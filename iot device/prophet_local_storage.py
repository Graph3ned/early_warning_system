"""
Local-first storage for Prophet forecasts on Raspberry Pi.
Forecast runs are stored in SQLite first; Firebase sync runs when online (same pattern as sensor readings).
Uses the same DB file as database_storage (ocr_live/sensor_readings.db).
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from database_storage import DB_FILE


def init_forecast_tables():
    """Create forecast tables if they do not exist."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecast_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                firebase_synced INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecast_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                parameter TEXT NOT NULL,
                date_str TEXT NOT NULL,
                time_str TEXT NOT NULL,
                predicted REAL NOT NULL,
                lower_real REAL NOT NULL,
                upper_real REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecast_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                parameter TEXT NOT NULL,
                mae REAL NOT NULL,
                rmse REAL NOT NULL,
                mape REAL
            )
        """)

        # Backwards-compatible migration: add MAPE column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE forecast_metrics ADD COLUMN mape REAL")
        except Exception:
            # Column may already exist; ignore errors
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecast_status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                system TEXT NOT NULL,
                reason TEXT,
                latest_run_id TEXT,
                last_forecast_at TEXT,
                firebase_synced INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecast_trend (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                date_key TEXT NOT NULL,
                is_latest INTEGER DEFAULT 0,
                payload_json TEXT NOT NULL,
                firebase_synced INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error initializing forecast tables: {e}")
        return False


def store_forecast_run(run_id: str, status: str, reason: str) -> bool:
    """Record a forecast run (firebase_synced=0 until pushed)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO forecast_runs (run_id, created_at, status, reason, firebase_synced)
            VALUES (?, ?, ?, ?, 0)
        """, (run_id, datetime.now().isoformat(), status, reason))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error storing forecast run: {e}")
        return False


def store_forecast_points(run_id: str, parameter: str, forecast_rows: List[Tuple[str, str, float, float, float]]) -> bool:
    """Store forecast points. forecast_rows: list of (date_str, time_str, predicted, lower, upper)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO forecast_points (run_id, parameter, date_str, time_str, predicted, lower_real, upper_real)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [(run_id, parameter, r[0], r[1], r[2], r[3], r[4]) for r in forecast_rows])
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error storing forecast points: {e}")
        return False


def store_forecast_metrics(run_id: str, parameter: str, mae: float, rmse: float, mape: float) -> bool:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO forecast_metrics (run_id, parameter, mae, rmse, mape) VALUES (?, ?, ?, ?, ?)
        """, (run_id, parameter, mae, rmse, mape))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error storing forecast metrics: {e}")
        return False


def store_forecast_status_local(system: str, reason: str, latest_run_id: Optional[str] = None) -> bool:
    """Upsert the single forecast_status row (id=1)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        last_forecast_at = datetime.utcnow().isoformat() + "Z" if latest_run_id else None
        cursor.execute("""
            REPLACE INTO forecast_status (id, system, reason, latest_run_id, last_forecast_at, firebase_synced)
            VALUES (1, ?, ?, ?, ?, 0)
        """, (system, reason, latest_run_id, last_forecast_at))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error storing forecast status: {e}")
        return False


def store_forecast_trend_local(run_id: str, date_key: str, payload: Dict[str, Any]) -> bool:
    """Store trend payload for a run and optionally as latest."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        payload_json = json.dumps(payload)
        cursor.execute("""
            INSERT INTO forecast_trend (run_id, date_key, is_latest, payload_json, firebase_synced)
            VALUES (?, ?, 0, ?, 0)
        """, (run_id, date_key, payload_json))
        cursor.execute("""
            UPDATE forecast_trend SET is_latest = 0
        """)
        cursor.execute("""
            INSERT INTO forecast_trend (run_id, date_key, is_latest, payload_json, firebase_synced)
            VALUES (?, 'latest', 1, ?, 0)
        """, (run_id, payload_json))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error storing forecast trend: {e}")
        return False


def get_unsynced_forecast_runs() -> List[str]:
    """Return list of run_id that have firebase_synced=0."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT run_id FROM forecast_runs WHERE firebase_synced = 0 ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception as e:
        print(f"Error getting unsynced forecast runs: {e}")
        return []


def get_forecast_run_points(run_id: str) -> Dict[str, List[Tuple[str, str, float, float, float]]]:
    """Return { parameter: [ (date_str, time_str, predicted, lower, upper), ... ] }."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT parameter, date_str, time_str, predicted, lower_real, upper_real
            FROM forecast_points WHERE run_id = ? ORDER BY parameter, date_str, time_str
        """, (run_id,))
        rows = cursor.fetchall()
        conn.close()
        result = {}
        for r in rows:
            param, date_str, time_str, pred, lo, hi = r
            if param not in result:
                result[param] = []
            result[param].append((date_str, time_str, pred, lo, hi))
        return result
    except Exception as e:
        print(f"Error getting forecast points: {e}")
        return {}


def get_forecast_run_metrics(run_id: str) -> Dict[str, Tuple[float, float, float]]:
    """Return { parameter: (mae, rmse, mape) } (mape may be None)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT parameter, mae, rmse, mape FROM forecast_metrics WHERE run_id = ?", (run_id,))
            rows = cursor.fetchall()
            conn.close()
            return {r[0]: (r[1], r[2], r[3]) for r in rows}
        except Exception:
            # Fallback for legacy databases without mape column
            cursor.execute("SELECT parameter, mae, rmse FROM forecast_metrics WHERE run_id = ?", (run_id,))
            rows = cursor.fetchall()
            conn.close()
            return {r[0]: (r[1], r[2], None) for r in rows}
    except Exception as e:
        print(f"Error getting forecast metrics: {e}")
        return {}


def get_forecast_status_local() -> Optional[Dict[str, Any]]:
    """Return { system, reason, latest_run_id, last_forecast_at } or None."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT system, reason, latest_run_id, last_forecast_at FROM forecast_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {"system": row[0], "reason": row[1], "latest_run_id": row[2], "last_forecast_at": row[3]}
    except Exception as e:
        print(f"Error getting forecast status: {e}")
        return None


def get_forecast_trend_for_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Return trend payload (dict) for the run from forecast_trend (date_key row, not latest)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT payload_json FROM forecast_trend WHERE run_id = ? AND is_latest = 0 LIMIT 1",
            (run_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return json.loads(row[0])
    except Exception as e:
        print(f"Error getting forecast trend: {e}")
        return None


def get_forecast_trend_date_and_payload(run_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Return (date_key, payload) for pushing trend to Firebase."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date_key, payload_json FROM forecast_trend WHERE run_id = ? AND is_latest = 0 LIMIT 1",
            (run_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return (row[0], json.loads(row[1]))
    except Exception as e:
        print(f"Error getting forecast trend for push: {e}")
        return None


def mark_forecast_run_synced(run_id: str) -> bool:
    """Set firebase_synced=1 for this run and related status/trend."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE forecast_runs SET firebase_synced = 1 WHERE run_id = ?", (run_id,))
        cursor.execute("UPDATE forecast_status SET firebase_synced = 1 WHERE id = 1")
        cursor.execute("UPDATE forecast_trend SET firebase_synced = 1 WHERE run_id = ?", (run_id,))
        cursor.execute("UPDATE forecast_trend SET firebase_synced = 1 WHERE is_latest = 1")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking forecast run synced: {e}")
        return False
