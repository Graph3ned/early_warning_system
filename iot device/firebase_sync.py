"""
Push unsynced sensor readings from local SQLite to Firebase Realtime Database.
"""

import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
from database_storage import get_unsynced_readings, mark_as_synced

# =====================================================
# CONFIGURATION
# =====================================================
FIREBASE_KEY = "firebase_key.json"
DATABASE_URL = "https://early-waring-system-default-rtdb.asia-southeast1.firebasedatabase.app/"

# =====================================================
# INITIALIZE FIREBASE (SAFE)
# =====================================================
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_KEY)
    firebase_admin.initialize_app(cred, {
        "databaseURL": DATABASE_URL
    })

root_ref = db.reference("sensor_data")

# =====================================================
# PUSH FUNCTION (FROM DATABASE TO FIREBASE)
# =====================================================
def push_to_firebase():
    """
    Read unsynced readings from local database and push to Firebase.
    Returns the number of readings successfully pushed.
    """
    # Get unsynced readings from database
    unsynced_readings = get_unsynced_readings()
    
    if not unsynced_readings:
        print("[INFO] No unsynced readings to push")
        return 0

    pushed_count = 0
    failed_ids = []

    for reading in unsynced_readings:
        reading_id, timestamp_str, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated, aeration_status, sync_status = reading
        
        try:
            # Parse timestamp and convert to ISO format for Firebase key
            # Handle both ISO format and other formats
            try:
                if 'T' in timestamp_str:
                    # Already in ISO format
                    timestamp_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    # Try parsing other formats
                    timestamp_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except:
                # Fallback: use current time if parsing fails
                timestamp_dt = datetime.now()
            
            # Format as ISO timestamp for Firebase key (e.g., "2026-02-01T10:00:00")
            firebase_key = timestamp_dt.strftime("%Y-%m-%dT%H:%M:%S")
            
            # Create payload according to required structure
            payload = {
                "temperature": float(temperature),
                "ph": float(ph),
                "dissolved_oxygen": float(dissolved_oxygen),
                "ec": float(ec)
            }
            
            if salinity is not None:
                payload["salinity"] = float(salinity)
            if do_salinity_compensated is not None:
                payload["do_salinity_compensated"] = float(do_salinity_compensated)
            if aeration_status:
                payload["aeration_status"] = aeration_status
            
            # Push to Firebase under sensor_data/{timestamp}
            root_ref.child(firebase_key).set(payload)
            
            # Mark as synced in database
            if mark_as_synced(reading_id):
                pushed_count += 1
                print(f"☁️ Pushed to Firebase: {firebase_key} | TEMP={temperature}°C, pH={ph}, DO={dissolved_oxygen}mg/L, EC={ec} mS/cm")
            else:
                failed_ids.append(reading_id)
                print(f"[WARN] Failed to mark reading {reading_id} as synced")
                
        except Exception as e:
            failed_ids.append(reading_id)
            print(f"[ERROR] Failed to push reading {reading_id} to Firebase: {e}")
    
    if pushed_count > 0:
            print(f"[INFO] Successfully pushed {pushed_count} reading(s) to Firebase")
    
    if failed_ids:
        print(f"[WARN] Failed to push {len(failed_ids)} reading(s)")
    
    return pushed_count

# =====================================================
# MANUAL SYNC (FOR TESTING)
# =====================================================
if __name__ == "__main__":
    print("[INFO] Starting Firebase sync...")
    count = push_to_firebase()
    print(f"[INFO] Sync complete. Pushed {count} reading(s)")
