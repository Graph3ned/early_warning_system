"""
Local SQLite database for recipient management.
Handles CRUD operations on recipient phone numbers stored locally.
"""

import sqlite3
from datetime import datetime
import re

# =====================================================
# CONFIGURATION
# =====================================================
DB_FILE = "recipients.db"
DEFAULT_PHONE = "+639123456789"  # Default fallback phone number
DEFAULT_NAME = "Default Admin"

# =====================================================
# PHONE NUMBER VALIDATION
# =====================================================
def validate_phone_number(phone):
    """
    Validate phone number format (e.g., +63xxxxxxxxxx).

    Args:
        phone: Phone number string

    Returns:
        bool: True if valid, False otherwise
    """
    if not phone:
        return False

    # Pattern: + followed by country code and 9-12 digits
    pattern = r'^\+[1-9]\d{9,12}$'
    return bool(re.match(pattern, phone))


def format_phone_number(phone):
    """
    Format phone number to standard format.
    Removes spaces, dashes, and ensures + prefix.

    Args:
        phone: Phone number string

    Returns:
        str: Formatted phone number or None if invalid
    """
    if not phone:
        return None

    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)

    # Ensure + prefix
    if not cleaned.startswith('+'):
        # If starts with 0, replace with country code
        if cleaned.startswith('0'):
            cleaned = '+63' + cleaned[1:]
        else:
            cleaned = '+' + cleaned

    # Validate
    if validate_phone_number(cleaned):
        return cleaned

    return None


# =====================================================
# DATABASE INITIALIZATION
# =====================================================
def init_database():
    """Initialize SQLite database and create table if it doesn't exist"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firebase_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index on firebase_id for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_firebase_id ON recipients(firebase_id)
        """)

        # Create index on active for faster filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_active ON recipients(active)
        """)

        conn.commit()
        conn.close()
        print(f"[INFO] Recipients database initialized: {DB_FILE}")
        return True
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return False


def ensure_default_recipient():
    """
    Ensure at least one active recipient exists in the database.
    Inserts default recipient if no active recipients found.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check if any active recipients exist
        cursor.execute("SELECT COUNT(*) FROM recipients WHERE active = 1")
        count = cursor.fetchone()[0]

        if count == 0:
            # Check if default already exists (inactive)
            cursor.execute("""
                SELECT id FROM recipients
                WHERE phone = ? AND firebase_id = 'default'
            """, (DEFAULT_PHONE,))

            existing = cursor.fetchone()

            if existing:
                # Reactivate existing default
                cursor.execute("""
                    UPDATE recipients
                    SET active = 1, updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), existing[0]))
                print(f"[INFO] Reactivated default recipient: {DEFAULT_PHONE}")
            else:
                # Insert new default recipient
                cursor.execute("""
                    INSERT INTO recipients (firebase_id, name, phone, active, created_at, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                """, (
                    'default',
                    DEFAULT_NAME,
                    DEFAULT_PHONE,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                print(f"[INFO] Inserted default recipient: {DEFAULT_PHONE}")

                conn.commit()

        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to ensure default recipient: {e}")
        return False


# =====================================================
# CRUD OPERATIONS
# =====================================================
def create_recipient(firebase_id, name, phone, active=1):
    """
    Create a new recipient in local database.

    Args:
        firebase_id: Unique Firebase ID
        name: Recipient name
        phone: Phone number (will be validated and formatted)
        active: Active status (1 = active, 0 = inactive)

    Returns:
        int: ID of created recipient, or None on failure
    """
    try:
        # Validate and format phone number
        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            print(f"[WARN] Invalid phone number format: {phone}")
            return None

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO recipients (firebase_id, name, phone, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            firebase_id,
            name,
            formatted_phone,
            active,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))

        recipient_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"[INFO] Created recipient: {name} ({formatted_phone})")
        return recipient_id
    except sqlite3.IntegrityError:
        print(f"[WARN] Recipient with firebase_id '{firebase_id}' already exists")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to create recipient: {e}")
        return None


def get_recipient_by_firebase_id(firebase_id):
    """
    Get recipient by Firebase ID.

    Args:
        firebase_id: Firebase ID

    Returns:
        tuple: (id, firebase_id, name, phone, active, created_at, updated_at) or None
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, firebase_id, name, phone, active, created_at, updated_at
            FROM recipients
            WHERE firebase_id = ?
        """, (firebase_id,))

        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"[ERROR] Failed to get recipient: {e}")
        return None


def update_recipient(firebase_id, name=None, phone=None, active=None):
    """
    Update recipient by Firebase ID.

    Args:
        firebase_id: Firebase ID
        name: New name (optional)
        phone: New phone number (optional, will be validated)
        active: New active status (optional)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if phone is not None:
            formatted_phone = format_phone_number(phone)
            if not formatted_phone:
                print(f"[WARN] Invalid phone number format: {phone}")
                conn.close()
                return False
            updates.append("phone = ?")
            params.append(formatted_phone)

        if active is not None:
            updates.append("active = ?")
            params.append(active)

        if not updates:
            conn.close()
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(firebase_id)

        cursor.execute(f"""
            UPDATE recipients
            SET {', '.join(updates)}
            WHERE firebase_id = ?
        """, params)

        conn.commit()
        conn.close()

        if cursor.rowcount > 0:
            print(f"[INFO] Updated recipient: {firebase_id}")
            return True
        else:
            print(f"[WARN] Recipient not found: {firebase_id}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to update recipient: {e}")
        return False


def delete_recipient(firebase_id, soft_delete=True):
    """
    Delete recipient (soft delete by default).

    Args:
        firebase_id: Firebase ID
        soft_delete: If True, set active=0; if False, hard delete

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if soft_delete:
            return update_recipient(firebase_id, active=0)
        else:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM recipients WHERE firebase_id = ?", (firebase_id,))

            conn.commit()
            conn.close()

            if cursor.rowcount > 0:
                print(f"[INFO] Deleted recipient: {firebase_id}")
                return True
            else:
                print(f"[WARN] Recipient not found: {firebase_id}")
                return False
    except Exception as e:
        print(f"[ERROR] Failed to delete recipient: {e}")
        return False


# =====================================================
# QUERY OPERATIONS
# =====================================================
def get_all_recipients(active_only=True):
    """
    Get all recipients from local database.

    Args:
        active_only: If True, return only active recipients

    Returns:
        list: List of tuples (id, firebase_id, name, phone, active, created_at, updated_at)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        if active_only:
            cursor.execute("""
                SELECT id, firebase_id, name, phone, active, created_at, updated_at
                FROM recipients
                WHERE active = 1
                ORDER BY name
            """)
        else:
            cursor.execute("""
                SELECT id, firebase_id, name, phone, active, created_at, updated_at
                FROM recipients
                ORDER BY name
            """)

        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"[ERROR] Failed to get recipients: {e}")
        return []


def get_active_phone_numbers():
    """
    Get list of active phone numbers for SMS alerts.

    Returns:
        list: List of phone number strings
    """
    try:
        recipients = get_all_recipients(active_only=True)
        return [recipient[3] for recipient in recipients]  # phone is at index 3
    except Exception as e:
        print(f"[ERROR] Failed to get active phone numbers: {e}")
        return []


def get_recipient_count(active_only=True):
    """
    Get count of recipients.

    Args:
        active_only: If True, count only active recipients

    Returns:
        int: Count of recipients
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        if active_only:
            cursor.execute("SELECT COUNT(*) FROM recipients WHERE active = 1")
        else:
            cursor.execute("SELECT COUNT(*) FROM recipients")

        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"[ERROR] Failed to get recipient count: {e}")
        return 0


# =====================================================
# INITIALIZATION
# =====================================================
if __name__ == "__main__":
    # Initialize database and ensure default recipient
    init_database()
    ensure_default_recipient()
    print(f"[INFO] Active recipients: {get_recipient_count(active_only=True)}")
