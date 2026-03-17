"""
SQLite persistence for sensor readings.
Provides initialization, storage, retrieval, and sync-status handling for the early warning system.
"""

import os
import sqlite3
from datetime import datetime

# Database path: under early_warning_system/ocr_live, alongside modified_ocr_live and reading_processor.
_this_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_this_dir, "ocr_live", "sensor_readings.db")

def init_database():
    """Initialize SQLite database and create table if it doesn't exist"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                temperature REAL NOT NULL,
                ph REAL,
                dissolved_oxygen REAL NOT NULL,
                ec REAL,
                salinity REAL,
                do_salinity_compensated REAL,
                aeration_status TEXT,
                sync_status INTEGER DEFAULT 0
            )
        """)
        
        # Add salinity column to existing table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE sensor_readings ADD COLUMN salinity REAL")
            print("[INFO] Added salinity column to existing table")
        except sqlite3.OperationalError:
            pass
        
        # Add aeration_status column to existing table if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE sensor_readings ADD COLUMN aeration_status TEXT")
            print("[INFO] Added aeration_status column to existing table")
        except sqlite3.OperationalError:
            pass
        
        # Add do_salinity_compensated column (Weiss DO salinity compensation) if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE sensor_readings ADD COLUMN do_salinity_compensated REAL")
            print("[INFO] Added do_salinity_compensated column to existing table")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()
        print(f"[INFO] Database initialized: {DB_FILE}")
        return True
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return False

def store_reading(temperature, ph, dissolved_oxygen, ec, aeration_status=None, do_salinity_compensated=None, salinity=None):
    """
    Store sensor reading in SQLite database.
    
    Args:
        temperature: Temperature value (float)
        ph: pH value (float)
        dissolved_oxygen: Dissolved oxygen value in mg/L (float)
        ec: Electrical conductivity in mS/cm (float)
        aeration_status: Aeration status ("ACTIVATED" or "DEACTIVATED" or None)
        do_salinity_compensated: DO mg/L after Weiss salinity compensation (float or None)
        salinity: Salinity in ppt from EC conversion (float or None)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Small busy-timeout so short locks don't immediately fail
        conn = sqlite3.connect(DB_FILE, timeout=5.0)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sensor_readings (timestamp, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated, aeration_status, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (datetime.now().isoformat(), temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated, aeration_status))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        # Log SQLite error in a way that will also appear in ocr.log
        print(f"[WARN] SQLite error while storing reading into '{DB_FILE}': {e}")
        print(f"[ERROR] Failed to store reading in database: {e}")
        return False

def get_recent_readings(limit=100):
    """
    Retrieve recent sensor readings from database.
    
    Args:
        limit: Maximum number of readings to retrieve (default: 100)
    
    Returns:
        list: List of tuples (id, timestamp, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated, aeration_status, sync_status)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated, aeration_status, sync_status
            FROM sensor_readings
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"[ERROR] Failed to retrieve readings from database: {e}")
        return []

def get_unsynced_readings():
    """
    Retrieve all readings that haven't been synced (sync_status = 0).
    
    Returns:
        list: List of tuples (id, timestamp, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated, aeration_status, sync_status)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated, aeration_status, sync_status
            FROM sensor_readings
            WHERE sync_status = 0
            ORDER BY timestamp ASC
        """)
        
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"[ERROR] Failed to retrieve unsynced readings: {e}")
        return []

def mark_as_synced(reading_id):
    """
    Mark a reading as synced by setting sync_status = 1.
    
    Args:
        reading_id: The ID of the reading to mark as synced
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE sensor_readings
            SET sync_status = 1
            WHERE id = ?
        """, (reading_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to mark reading as synced: {e}")
        return False

def get_reading_count():
    """
    Get the total number of readings in the database.
    
    Returns:
        int: Number of readings, or 0 on error
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"[ERROR] Failed to get reading count: {e}")
        return 0


def get_sensor_data_for_prophet(limit=None):
    """
    Retrieve sensor readings for Prophet forecasting, ordered by timestamp ascending.
    Returns all columns needed for Prophet: timestamp, temperature, ph, dissolved_oxygen,
    ec, salinity, do_salinity_compensated.
    
    Args:
        limit: Max number of rows (default None = all).
    
    Returns:
        list: List of tuples (timestamp_iso, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated).
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        if limit:
            cursor.execute("""
                SELECT timestamp, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated
                FROM sensor_readings
                ORDER BY timestamp ASC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT timestamp, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated
                FROM sensor_readings
                ORDER BY timestamp ASC
            """)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"[ERROR] Failed to retrieve sensor data for Prophet: {e}")
        return []

