"""
Push unsynced sensor readings from local SQLite to Firebase Realtime Database.

This module is designed to be non-blocking for the OCR reading loop:
- The OCR loop calls `request_firebase_sync()`, which enqueues work.
- A single background worker pushes a small batch when network is reachable.
- Failures trigger a circuit breaker to avoid hammering Firebase while offline.
"""

import os
import socket
import threading
import time
from datetime import datetime
from typing import Optional

import firebase_admin
from firebase_admin import credentials, db

from database_storage import get_unsynced_readings, mark_as_synced

# =====================================================
# CONFIGURATION
# =====================================================
FIREBASE_KEY = "firebase_key.json"
DATABASE_URL = "https://early-waring-system-default-rtdb.asia-southeast1.firebasedatabase.app/"

# ------------------------------
# Sync behavior tuning (env overrides)
# ------------------------------
# How many unsynced readings to try per push attempt.
FIREBASE_SYNC_BATCH_SIZE = int(os.environ.get("FIREBASE_SYNC_BATCH_SIZE", "10"))
# After a failed push attempt (timeout/reset), wait N seconds before trying again.
FIREBASE_SYNC_COOLDOWN_SECONDS = int(os.environ.get("FIREBASE_SYNC_COOLDOWN_SECONDS", "300"))
# Quick TCP check timeout before attempting Firebase network calls.
FIREBASE_CONNECTIVITY_TIMEOUT_SECONDS = float(os.environ.get("FIREBASE_CONNECTIVITY_TIMEOUT_SECONDS", "3"))
# Firebase (Google) auth endpoint that commonly appears in failures.
FIREBASE_CONNECTIVITY_HOST = os.environ.get("FIREBASE_CONNECTIVITY_HOST", "oauth2.googleapis.com")
FIREBASE_CONNECTIVITY_PORT = int(os.environ.get("FIREBASE_CONNECTIVITY_PORT", "443"))

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
# INTERNAL STATE (worker + circuit breaker)
# =====================================================
_sync_worker_thread: Optional[threading.Thread] = None
_sync_worker_thread_lock = threading.Lock()
_sync_request_event = threading.Event()
_sync_run_lock = threading.Lock()  # "single-flight" lock

_circuit_break_until = 0.0
_last_push_had_network_failure = False


def _is_probable_network_error(exc: BaseException) -> bool:
    s = str(exc).lower()
    # Match common patterns seen in your logs.
    network_markers = [
        "timed out",
        "read timed out",
        "connection reset",
        "connection aborted",
        "connection refused",
        "broken pipe",
        "ssl",
        "eof occurred in violation of protocol",
    ]
    return any(m in s for m in network_markers)


def _can_reach_firebase() -> bool:
    """
    Fail fast: attempt a short TCP connection to a known Firebase/Google endpoint.
    This avoids entering long Firebase SDK timeouts when the network is down.
    """
    try:
        with socket.create_connection(
            (FIREBASE_CONNECTIVITY_HOST, FIREBASE_CONNECTIVITY_PORT),
            timeout=FIREBASE_CONNECTIVITY_TIMEOUT_SECONDS,
        ):
            return True
    except Exception:
        return False


def _trigger_circuit_break() -> None:
    global _circuit_break_until
    _circuit_break_until = time.time() + FIREBASE_SYNC_COOLDOWN_SECONDS
    print(f"[FIREBASE_SYNC] Circuit breaker active for {FIREBASE_SYNC_COOLDOWN_SECONDS}s (until {_circuit_break_until:.0f})")


def request_firebase_sync() -> bool:
    """
    Enqueue Firebase sync work for the background worker.
    Returns True if a sync request was accepted (not in cooldown).
    """
    now = time.time()
    if now < _circuit_break_until:
        return False

    with _sync_worker_thread_lock:
        global _sync_worker_thread
        if _sync_worker_thread is None or not _sync_worker_thread.is_alive():
            _sync_worker_thread = threading.Thread(target=_firebase_sync_worker_loop, daemon=True)
            _sync_worker_thread.start()

    _sync_request_event.set()
    return True


def _firebase_sync_worker_loop() -> None:
    while True:
        _sync_request_event.wait()
        _sync_request_event.clear()

        # Ensure only one sync attempt is running at a time.
        with _sync_run_lock:
            if time.time() < _circuit_break_until:
                continue

            # Fail fast when offline.
            if not _can_reach_firebase():
                print("[FIREBASE_SYNC] Network unreachable; skipping sync attempt (cooldown will start).")
                _trigger_circuit_break()
                continue

            try:
                push_to_firebase(batch_size=FIREBASE_SYNC_BATCH_SIZE)
            except Exception:
                _last_push_had_network_failure_local = True
            else:
                _last_push_had_network_failure_local = _last_push_had_network_failure

            if _last_push_had_network_failure_local:
                _trigger_circuit_break()


# =====================================================
# PUSH FUNCTION (FROM DATABASE TO FIREBASE)
# =====================================================
def push_to_firebase(batch_size: Optional[int] = None) -> int:
    """
    Read unsynced readings from local database and push to Firebase.
    Returns the number of readings successfully pushed.
    """
    global _last_push_had_network_failure
    _last_push_had_network_failure = False

    # Get unsynced readings from database
    unsynced_readings = get_unsynced_readings()
    
    if not unsynced_readings:
        print("[INFO] No unsynced readings to push")
        return 0

    if batch_size is not None and batch_size > 0:
        unsynced_readings = unsynced_readings[:batch_size]

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
            if _is_probable_network_error(e):
                # Stop the batch immediately on network failures, so we can
                # wait for the next sync window (circuit breaker handles the cooldown).
                _last_push_had_network_failure = True
                break
    
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
