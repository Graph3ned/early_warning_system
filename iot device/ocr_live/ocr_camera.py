"""
Camera open/close for YK-100 live OCR.
Uses locked settings from ocr_config (AF, focus, AE, exposure) so all scripts share the same camera setup.
"""

import time
import cv2
import subprocess

from ocr_config import (
    CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_AUTOFOCUS,
    CAMERA_FOCUS,
    CAMERA_AUTO_EXPOSURE,
    CAMERA_EXPOSURE,
    V4L2_EXPOSURE_ABSOLUTE,
    CAMERA_SHARPNESS,
    CAMERA_BUFFERSIZE,
)

def v4l2_set(ctrl, val):
    subprocess.run(
        ["v4l2-ctl", "-d", "/dev/video0", f"--set-ctrl={ctrl}={val}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _v4l2_set_sharpness(value):
    """Set camera sharpness via V4L2. Tries 'sharpness' then 'sharpness_absolute'; no-op if unsupported."""
    for ctrl in ("sharpness", "sharpness_absolute"):
        r = subprocess.run(
            ["v4l2-ctl", "-d", "/dev/video0", f"--set-ctrl={ctrl}={value}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if r.returncode == 0:
            return
    # Sharpness control not available on this camera; skip.

WARMUP_SECONDS = 2.0


def safe_set(cap, prop, value, name="", verbose=True):
    ok = cap.set(prop, value)
    if name and verbose:
        print(f"[INFO] set {name}={value}" if ok else f"[WARN] set {name}={value}")
    return ok


def safe_get(cap, prop, name=""):
    val = cap.get(prop)
    if name:
        print(f"[INFO] {name}={val}")
    return val


def apply_camera_settings(cap, verbose=True):
    """
    Apply locked camera settings from ocr_config to an open VideoCapture.
    Call this after opening the camera so all scripts use the same AF, focus, AE, exposure.
    """
    cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFERSIZE)
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    safe_set(cap, cv2.CAP_PROP_FOURCC, fourcc, "FOURCC(MJPG)", verbose)
    safe_set(cap, cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH, "WIDTH", verbose)
    safe_set(cap, cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT, "HEIGHT", verbose)
    safe_set(cap, cv2.CAP_PROP_AUTOFOCUS, 1 if CAMERA_AUTOFOCUS else 0, "AUTOFOCUS", verbose)
    safe_set(cap, cv2.CAP_PROP_FOCUS, CAMERA_FOCUS, "FOCUS", verbose)
    safe_set(cap, cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if CAMERA_AUTO_EXPOSURE else 0.25, "AUTO_EXPOSURE", verbose)
    safe_set(cap, cv2.CAP_PROP_EXPOSURE, CAMERA_EXPOSURE, "EXPOSURE", verbose)
    # V4L2: WB manual; sharpness (if supported); autofocus kick.
    v4l2_set("white_balance_automatic", 0)
    _v4l2_set_sharpness(CAMERA_SHARPNESS)
    v4l2_set("focus_automatic_continuous", 0)
    if CAMERA_AUTOFOCUS:
        for _ in range(2):
            cap.read()
        time.sleep(0.15)
        v4l2_set("focus_automatic_continuous", 1)
    # Don't set manual exposure here — start with AE so first frames aren't black; lock after warm-up.


def initialize_camera(preview_mode=False):
    """
    Open camera and apply locked settings from ocr_config. Warm-up is always done.
    - preview_mode=False (default): full locked settings (MJPG, AF, focus, AE, exposure).
    - preview_mode=True: resolution + warm-up only (e.g. for tools that want different controls).
    """
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam")
        return None

    safe_set(cap, cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH, "WIDTH")
    safe_set(cap, cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT, "HEIGHT")
    if not preview_mode:
        apply_camera_settings(cap)
    else:
        v4l2_set("focus_automatic_continuous", 0)
        v4l2_set("white_balance_automatic", 0)

    # Start with auto exposure so the image isn't black; camera needs AE to settle first.
    v4l2_set("auto_exposure", 3)  # 3 = auto (typical V4L2); 1 = manual
    print(f"Warming up camera for {WARMUP_SECONDS} seconds (AE on)...")
    t0 = time.time()
    while time.time() - t0 < WARMUP_SECONDS:
        ret, frame = cap.read()
        if not ret:
            continue
    # Now lock manual exposure to avoid ramp to 2047 (blur). Use V4L2_EXPOSURE_ABSOLUTE from config.
    v4l2_set("auto_exposure", 1)
    v4l2_set("exposure_time_absolute", V4L2_EXPOSURE_ABSOLUTE)
    # Kick autofocus: driver often ignores AF until toggled. Off -> on so preview is sharp when AF is enabled.
    if CAMERA_AUTOFOCUS:
        v4l2_set("focus_automatic_continuous", 0)
        for _ in range(3):
            cap.read()
        v4l2_set("focus_automatic_continuous", 1)
    print("Camera warm-up done (exposure locked to manual)")

    return cap


def release_camera(cap):
    if cap is not None:
        cap.release()
