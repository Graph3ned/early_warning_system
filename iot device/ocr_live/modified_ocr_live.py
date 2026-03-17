"""
YK-100 Live OCR main entry point.

Run from project root: python early_warning_system/ocr_live/modified_ocr_live.py
Use --no-preview for SSH or headless (no camera window; lower CPU). Use --preview to force preview.
"""

import argparse
import sys
from pathlib import Path

# Ensure early_warning_system folder is on path (database_storage, gsm_alert, esp8266, etc.)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import cv2
import numpy as np
import threading
import time
import subprocess
from datetime import datetime, date

# Parse preview option before other imports that might use display
_parser = argparse.ArgumentParser(description="YK-100 Live OCR")
_parser.add_argument("--no-preview", action="store_true", help="No camera window (for SSH/headless, less lag)")
_parser.add_argument("--preview", action="store_true", help="Show camera preview (default if no flag)")
_args = _parser.parse_args()
if _args.no_preview:
    show_preview = False
elif _args.preview:
    show_preview = True
else:
    try:
        ans = input("Show camera preview? (y/n, default y): ").strip().lower() or "y"
        show_preview = ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        show_preview = False

from database_storage import init_database
from prophet_local_storage import init_forecast_tables
from recipient_manager import get_recipient_manager
from ocr_config import (
    setup,
    PARAMETERS,
    READING_INTERVAL,
    RECIPIENT_SYNC_INTERVAL,
    STABILIZATION_FRAMES,
    STABILIZATION_DELAY,
    OCR_FRAME_COUNT,
    OCR_FRAME_DELAY,
    MAX_INVALID_FRAMES_TOLERATED,
    RESULT_DISPLAY_SECONDS,
    DISPLAY_TILT_CORRECTION_DEG,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    PROPHET_SCRIPT_PATH,
    PROPHET_RUN_HOUR,
    PROPHET_RUN_MINUTE,
)
from ocr_engine import run_ocr, extract_numeric_value, correct_tilt
from ocr_camera import initialize_camera, release_camera
from ble_connection import start_ble_connection
from relay_control import init_relay, cleanup_relay
from fan_relay import init_fan_relay, cleanup_fan_relay
from reading_processor import ReadingProcessor
from firebase_device_status import run_periodic_device_status_update
from ocr_display import draw_preview_overlay, draw_result_overlay

# ---------------------------------------------------------------------------
# Window & init
# ---------------------------------------------------------------------------
if show_preview:
    cv2.namedWindow("YK-100 LIVE OCR", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("YK-100 LIVE OCR", CAMERA_WIDTH, CAMERA_HEIGHT)
init_database()
init_forecast_tables()

print("Initializing relay...")
init_relay()

print("Initializing CPU fan relay (Pi GPIO)...")
init_fan_relay()

print("Initializing recipient management system...")
try:
    recipient_manager = get_recipient_manager(auto_sync=True, sync_interval=RECIPIENT_SYNC_INTERVAL)
    print("Recipient management system initialized")
except Exception as e:
    print(f"[WARN] Recipient management initialization error: {e}")
    recipient_manager = None

start_ble_connection()


def _device_status_loop():
    """Daemon: every READING_INTERVAL seconds, refresh ESP connection, Pi temp, and write device_status."""
    while True:
        time.sleep(READING_INTERVAL)
        try:
            run_periodic_device_status_update()
        except Exception as e:
            print(f"[WARN] Periodic device status update failed: {e}")


_device_status_thread = threading.Thread(target=_device_status_loop, daemon=True)
_device_status_thread.start()

if show_preview:
    print("Live OCR running (press Q to quit)")
else:
    print("Live OCR running (no preview; stop with Ctrl+C)")
print("Camera will turn on every 3 minutes for readings")
print("Device status (ESP, reading status, Pi temp) updates every 3 minutes")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
cap = None
last_valid = {p: None for p in PARAMETERS}
last_ec_mScm = None
last_results = {p: None for p in PARAMETERS}
last_reading_time = 0
reading_processor = ReadingProcessor()
_last_prophet_run_date: date | None = None


def _preview_frame(frame):
    """Return frame with tilt correction applied for display (matches what OCR sees)."""
    if DISPLAY_TILT_CORRECTION_DEG != 0:
        return correct_tilt(frame, DISPLAY_TILT_CORRECTION_DEG)
    return frame


def _is_frame_value_invalid(v):
    """True if this frame's value for a parameter is invalid (cannot be used for median)."""
    return v is None or v == "--" or "?" in str(v or "")


def run_ocr_multiframe(setup, frames_for_ocr, last_valid, last_ec_mScm, parameters):
    """
    Run OCR on every captured frame with the same initial state, then combine:
    - For each parameter, up to MAX_INVALID_FRAMES_TOLERATED (e.g. 3) frames may be invalid;
      if more than that many frames have "?" or "--" or None, the param is invalid ("?").
    - Otherwise use median of numeric values from the valid frames only (robust to flicker).
    Returns (combined_results, combined_last_valid, combined_last_ec_mScm). EC is in mS/cm.
    """
    if not frames_for_ocr:
        return {p: "--" for p in parameters}, dict(last_valid) if last_valid else {p: None for p in parameters}, last_ec_mScm

    last_valid_init = dict(last_valid) if last_valid else {p: None for p in parameters}
    last_ec_init = last_ec_mScm
    all_results = []

    for frame in frames_for_ocr:
        if DISPLAY_TILT_CORRECTION_DEG != 0:
            frame = correct_tilt(frame, DISPLAY_TILT_CORRECTION_DEG)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        results_i, last_valid_i, last_ec_i, _ = run_ocr(setup, gray, last_valid_init, last_ec_init)
        all_results.append((results_i, last_valid_i, last_ec_i))

    combined = {}
    ec_values = []

    for p in parameters:
        vals = [r[0].get(p) for r in all_results]
        invalid_count = sum(1 for v in vals if _is_frame_value_invalid(v))
        if invalid_count > MAX_INVALID_FRAMES_TOLERATED:
            combined[p] = "?"
            continue
        valid_indices = [i for i, v in enumerate(vals) if not _is_frame_value_invalid(v)]
        nums = [extract_numeric_value(vals[i]) for i in valid_indices]
        if not nums or any(n is None for n in nums):
            combined[p] = "?"
            continue
        if p == "CON":
            ec_list = [all_results[i][2] for i in valid_indices if all_results[i][2] is not None]
            if not ec_list:
                combined[p] = "?"
            else:
                med_ec = float(np.median(ec_list))
                ec_values.append(med_ec)
                combined[p] = f"{med_ec:.2f} mS"
        else:
            med = float(np.median(nums))
            if p == "TEMP":
                combined[p] = f"{med:.1f}"
            elif p == "pH":
                combined[p] = f"{med:.2f}"
            elif p == "DO":
                combined[p] = f"{med:.2f}"
            else:
                combined[p] = f"{med:.1f}"

    combined_last_valid = all_results[0][1] if all_results and not any(combined.get(p) == "?" for p in parameters) else last_valid_init
    combined_last_ec_mScm = float(np.median(ec_values)) if ec_values else last_ec_init

    return combined, combined_last_valid, combined_last_ec_mScm


def _run_daily_prophet_if_due(camera_off: bool):
    """Run prophet_server_raspi.py once per day at 22:30 (local time), only when camera is off."""
    global _last_prophet_run_date

    if not camera_off:
        return

    now = datetime.now()
    today = now.date()

    if _last_prophet_run_date == today:
        return

    if (now.hour, now.minute) < (PROPHET_RUN_HOUR, PROPHET_RUN_MINUTE):
        return

    print("Starting scheduled daily Prophet forecasting run (prophet_server_raspi.py)...")
    try:
        subprocess.run([sys.executable, str(PROPHET_SCRIPT_PATH)], check=True)
        print("Scheduled daily Prophet forecasting run completed.")
    except Exception as e:
        print(f"[WARN] Scheduled Prophet forecasting run failed: {e}")
    finally:
        _last_prophet_run_date = today


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
while True:
    _run_daily_prophet_if_due(camera_off=(cap is None))

    current_time = time.time()
    time_since_last_reading = current_time - last_reading_time
    should_take_reading = time_since_last_reading >= READING_INTERVAL or last_reading_time == 0

    # Camera on demand
    if should_take_reading and cap is None:
        print("Turning on camera...")
        cap = initialize_camera()
        if cap is None:
            print("[ERROR] Failed to initialize camera, retrying in 10 seconds...")
            time.sleep(10)
            continue
        print(f"Stabilizing camera ({STABILIZATION_FRAMES * STABILIZATION_DELAY:.1f} seconds)...")
        for _ in range(STABILIZATION_FRAMES):
            ret, frame = cap.read()
            if ret and show_preview:
                overlay_s = _preview_frame(frame).copy()
                cv2.putText(overlay_s, "Stabilizing camera...", (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
                cv2.imshow("YK-100 LIVE OCR", overlay_s)
                cv2.waitKey(1)
            time.sleep(STABILIZATION_DELAY)
        print("Camera ready")

    if cap is not None:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Camera read failed, releasing and will retry...")
            release_camera(cap)
            cap = None
            time.sleep(1)
            continue
    else:
        # Placeholder when camera is off: dark gray (not black) so preview doesn't look broken
        frame = np.full((CAMERA_HEIGHT, CAMERA_WIDTH, 3), 40, dtype=np.uint8)
        ret = True

    overlay = _preview_frame(frame).copy()

    if should_take_reading and cap is not None:
        # Capture frames for OCR
        print("Capturing frames for OCR...")
        frames_for_ocr = []
        for frame_num in range(OCR_FRAME_COUNT):
            ret, frame_cap = cap.read()
            if ret:
                frames_for_ocr.append(frame_cap)
                if show_preview:
                    ov = _preview_frame(frame_cap).copy()
                    cv2.putText(ov, f"Capturing frame {frame_num + 1}/{OCR_FRAME_COUNT}...", (40, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    cv2.imshow("YK-100 LIVE OCR", ov)
                    cv2.waitKey(1)
                time.sleep(OCR_FRAME_DELAY)
            else:
                break
        if not frames_for_ocr:
            print("[WARN] Failed to capture frames, releasing camera...")
            release_camera(cap)
            cap = None
            time.sleep(1)
            continue

        frame = frames_for_ocr[len(frames_for_ocr) // 2]
        overlay = _preview_frame(frame).copy()
        if show_preview:
            cv2.putText(overlay, f"Processing OCR ({len(frames_for_ocr)} frames)...", (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            cv2.imshow("YK-100 LIVE OCR", overlay)
            cv2.waitKey(1)

        results, last_valid, last_ec_mScm = run_ocr_multiframe(setup, frames_for_ocr, last_valid, last_ec_mScm, PARAMETERS)

        for param in PARAMETERS:
            if results.get(param) and results.get(param) != "--" and "?" not in str(results.get(param, "")):
                last_results[param] = results.get(param)

        last_reading_time = current_time
        print(f"Reading taken at {time.strftime('%H:%M:%S')}")

        status = reading_processor.process(results, last_results, last_ec_mScm, recipient_manager)
        if status in ("no_data", "invalid_data"):
            for p in PARAMETERS:
                last_results[p] = None
            print("Turning off camera (device off or invalid data)...")
            release_camera(cap)
            cap = None
            continue

        print(f"Showing results, camera will turn off in {RESULT_DISPLAY_SECONDS:.0f} seconds...")
        display_start_time = time.time()
        if show_preview:
            while (time.time() - display_start_time) < RESULT_DISPLAY_SECONDS:
                ret, frame = cap.read()
                if ret:
                    overlay = _preview_frame(frame).copy()
                    draw_result_overlay(overlay, last_results, last_ec_mScm, setup, display_start_time, camera_on=(cap is not None))
                    cv2.imshow("YK-100 LIVE OCR", overlay)
                    cv2.waitKey(1)
                time.sleep(0.1)
        else:
            time.sleep(RESULT_DISPLAY_SECONDS)
        print("Turning off camera...")
        release_camera(cap)
        cap = None
        continue

    if show_preview:
        display_results = {p: (last_results[p] if last_results.get(p) else "--") for p in PARAMETERS}
        draw_preview_overlay(
            overlay,
            display_results,
            last_ec_mScm,
            cap is not None,
            should_take_reading,
            time_since_last_reading,
            setup=setup,
        )
        cv2.imshow("YK-100 LIVE OCR", overlay)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    # When camera is off, avoid tight loop (reduces CPU load on Raspberry Pi)
    if cap is None:
        time.sleep(0.1)

if cap is not None:
    release_camera(cap)
cleanup_fan_relay()
cleanup_relay()
if show_preview:
    cv2.destroyAllWindows()
print("OCR stopped")
