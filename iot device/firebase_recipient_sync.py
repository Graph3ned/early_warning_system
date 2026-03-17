"""
Firebase Realtime Database synchronization for recipient management.
Syncs recipient data from Firebase to local SQLite database.
"""

import firebase_admin
from firebase_admin import credentials, db
from recipient_storage import (
    get_recipient_by_firebase_id,
    create_recipient,
    update_recipient,
    ensure_default_recipient,
    init_database
)
import requests
from datetime import datetime

# =====================================================
# CONFIGURATION
# =====================================================
FIREBASE_KEY = "firebase_key.json"
DATABASE_URL = "https://early-waring-system-default-rtdb.asia-southeast1.firebasedatabase.app/"
FIREBASE_RECIPIENTS_PATH = "recipients"  # Path in Firebase Realtime Database
SYNC_INTERVAL_SECONDS = 300  # 5 minutes default sync interval

# =====================================================
# INTERNET CHECK
# =====================================================
def check_internet_connection():
    """
    Check if internet connection is available.
    
    Returns:
        bool: True if internet is available, False otherwise
    """
    try:
        # Try to connect to a reliable server with short timeout
        response = requests.get("https://www.google.com", timeout=5)
        return response.status_code == 200
    except:
        try:
            # Fallback: try Firebase URL
            response = requests.get(DATABASE_URL, timeout=5)
            return True
        except:
            return False

# =====================================================
# FIREBASE INITIALIZATION
# =====================================================
def init_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY)
            firebase_admin.initialize_app(cred, {
                "databaseURL": DATABASE_URL
            })
            print("[INFO] Firebase initialized")
            return True
        return True
    except Exception as e:
        print(f"[ERROR] Firebase initialization failed: {e}")
        return False

# =====================================================
# FIREBASE SYNC OPERATIONS
# =====================================================
def fetch_recipients_from_firebase():
    """
    Fetch all recipients from Firebase Realtime Database.
    
    Returns:
        dict: Dictionary of recipients keyed by Firebase ID, or None on error
    """
    try:
        root_ref = db.reference(FIREBASE_RECIPIENTS_PATH)
        recipients_data = root_ref.get()
        
        if recipients_data is None:
            print("[INFO] No recipients found in Firebase")
            return {}
        
        # Firebase returns a dict where keys are Firebase IDs
        # Convert to a more usable format
        recipients = {}
        for firebase_id, recipient_data in recipients_data.items():
            if isinstance(recipient_data, dict):
                recipients[firebase_id] = recipient_data
        
        print(f"📥 Fetched {len(recipients)} recipient(s) from Firebase")
        return recipients
    except Exception as e:
        print(f"[ERROR] Failed to fetch recipients from Firebase: {e}")
        return None

def sync_recipients_from_firebase():
    """
    Synchronize recipients from Firebase to local database.
    
    Returns:
        dict: Sync statistics {
            'fetched': int,
            'inserted': int,
            'updated': int,
            'errors': int
        }
    """
    stats = {
        'fetched': 0,
        'inserted': 0,
        'updated': 0,
        'errors': 0
    }
    
    # Check internet connection
    if not check_internet_connection():
        print("[WARN] No internet connection. Skipping Firebase sync.")
        return stats
    
    # Initialize Firebase
    if not init_firebase():
        stats['errors'] += 1
        return stats
    
    # Fetch recipients from Firebase
    firebase_recipients = fetch_recipients_from_firebase()
    
    if firebase_recipients is None:
        stats['errors'] += 1
        return stats
    
    stats['fetched'] = len(firebase_recipients)
    
    # Sync each recipient
    for firebase_id, recipient_data in firebase_recipients.items():
        try:
            # Extract recipient data (handle different Firebase structures)
            name = recipient_data.get('name', 'Unknown')
            phone = recipient_data.get('phone', '')
            active = recipient_data.get('active', True)
            
            # Convert active to integer (1 or 0)
            if isinstance(active, bool):
                active = 1 if active else 0
            elif isinstance(active, (int, str)):
                active = 1 if int(active) else 0
            else:
                active = 1
            
            # Check if recipient exists in local database
            local_recipient = get_recipient_by_firebase_id(firebase_id)
            
            if local_recipient is None:
                # Insert new recipient
                recipient_id = create_recipient(firebase_id, name, phone, active)
                if recipient_id:
                    stats['inserted'] += 1
                else:
                    stats['errors'] += 1
            else:
                # Update existing recipient
                # Only update if data has changed
                local_name, local_phone, local_active = local_recipient[2], local_recipient[3], local_recipient[4]
                
                if (local_name != name or 
                    local_phone != phone or 
                    local_active != active):
                    success = update_recipient(firebase_id, name=name, phone=phone, active=active)
                    if success:
                        stats['updated'] += 1
                    else:
                        stats['errors'] += 1
        
        except Exception as e:
            print(f"[ERROR] Failed to sync recipient {firebase_id}: {e}")
            stats['errors'] += 1
    
    return stats

def sync_recipients():
    """
    Main sync function: Syncs recipients from Firebase to local database.
    Ensures default recipient exists if no active recipients after sync.
    
    Returns:
        dict: Sync statistics
    """
    print("🔄 Starting recipient synchronization...")
    
    # Initialize local database
    init_database()
    
    # Sync from Firebase
    stats = sync_recipients_from_firebase()
    
    # Ensure default recipient exists (if no active recipients)
    ensure_default_recipient()
    
    # Print summary
    print("=" * 60)
    print("[INFO] Sync summary:")
    print(f"   Fetched from Firebase: {stats['fetched']}")
    print(f"   Inserted: {stats['inserted']}")
    print(f"   Updated: {stats['updated']}")
    print(f"   Errors: {stats['errors']}")
    print("=" * 60)
    
    return stats

# =====================================================
# CONTINUOUS SYNC (OPTIONAL)
# =====================================================
def sync_loop():
    """
    Continuously sync recipients at specified intervals.
    Run this in a separate thread if needed.
    """
    import time
    
    print("🔄 Starting recipient sync loop...")
    while True:
        try:
            sync_recipients()
            time.sleep(SYNC_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n🛑 Sync loop stopped")
            break
        except Exception as e:
            print(f"[ERROR] Error in sync loop: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

# =====================================================
# MANUAL SYNC (FOR TESTING)
# =====================================================
if __name__ == "__main__":
    print("[INFO] Starting recipient synchronization...")
    stats = sync_recipients()
    print("[INFO] Sync complete.")
