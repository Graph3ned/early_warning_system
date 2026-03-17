"""
Central configuration for YK-100 live OCR.

Defines camera settings, thresholds, calibrated digit boxes, and timing constants.
"""

import pickle
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MAIN_DIR = _THIS_DIR.parent

# =====================================================
# CAMERA (locked for all scripts: same AF, focus, AE, exposure)
# =====================================================
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_AUTOFOCUS = True
CAMERA_FOCUS = 20
CAMERA_AUTO_EXPOSURE = False
CAMERA_EXPOSURE = -6
# V4L2 exposure lock: camera often ignores OpenCV and ramps to 2047 (max) → long exposure, blur/haze.
# Used after a short AE warm-up so the image isn't black at startup. 180 = dark; 500–800 often OK; avoid 2047.
V4L2_EXPOSURE_ABSOLUTE = 1800
# Camera sharpness (V4L2). Range is device-dependent (v4l2-ctl -d /dev/video0 -L). Many use 0-255 or 0-300.
CAMERA_SHARPNESS = 300
CAMERA_BUFFERSIZE = 1

# Display tilt: if the LED appears tilted left in the camera view, set positive (e.g. 1.5 to 3.0)
# to rotate the image counter-clockwise before OCR. Degrees.
DISPLAY_TILT_CORRECTION_DEG = 0.0

# Setup (digit boxes calibration): only early_warning_system dir (ocr_live's parent)
_SETUP_DIR = _MAIN_DIR  # early_warning_system
SETUP_FILE = _SETUP_DIR / "yk100_digit_boxes_calibrated.pkl"

# =====================================================
# BLE
# =====================================================
BLE_ADDRESS = "C0:00:00:05:B8:8D"  # YK-100 MAC address

# =====================================================
# RELAY (IP/port in esp8266/esp8266_config.py)
# =====================================================

# =====================================================
# ALERTS
# =====================================================
NO_DATA_ALERT_PHONES = [
    "+639542677124", "+639941696073", "+639507304401", "+639078591556", "+639857919384",
]

# =====================================================
# SENSOR & THRESHOLDS (BFAR bangus cage culture optimum ranges)
# =====================================================
PARAMETERS = ["pH", "TEMP", "DO", "CON"]

# ---- DO (Dissolved Oxygen) mg/L ----
# Normal: >= 4; Warning: 2.5–<4; Critical: < 2.5
DO_NORMAL_MIN = 4.0
DO_CRITICAL_MAX = 2.5          # Critical when v < 2.5 (use strict < in logic)
DO_WARNING_SMS_MAX = 4.0       # Send SMS when v < 4.0 (warning or critical)
DO_RELAY_ON_MAX = 2.5          # Turn ON relay (aerator) when DO below critical
DO_RELAY_OFF_MIN = 3.0         # Turn OFF relay when DO >= 3.0 (hysteresis)
DO_COOLDOWN_WARNING_SEC = 30 * 60
DO_COOLDOWN_CRITICAL_SEC = 15 * 60

# ---- Temperature °C ----
# Normal: 26–30; Warning: 23–<26 or >30–35; Critical: < 23 or > 35
TEMP_NORMAL_MIN = 26.0
TEMP_NORMAL_MAX = 30.0
TEMP_WARNING_LOW_MIN = 23.0    # Warning low: 23–<26
TEMP_WARNING_HIGH_MAX = 35.0   # Warning high: >30–35
TEMP_CRITICAL_LOW_MAX = 23.0   # Critical: v < 23
TEMP_CRITICAL_HIGH_MIN = 35.0  # Critical: v > 35
TEMP_COOLDOWN_WARNING_SEC = 30 * 60
TEMP_COOLDOWN_CRITICAL_SEC = 15 * 60

# ---- pH ----
# Normal: 7.5–8.5; Warning: 6–<7.5 or 8.5–9.5; Critical: < 6 or > 9.5
PH_NORMAL_MIN = 7.5
PH_NORMAL_MAX = 8.5
PH_WARNING_MIN = 6.0           # Warning low: 6–<7.5
PH_WARNING_HIGH_MAX = 9.5      # Warning high: 8.5–9.5
PH_CRITICAL_LOW_MAX = 6.0      # Critical: v < 6
PH_CRITICAL_HIGH_MIN = 9.5     # Critical: v > 9.5
PH_COOLDOWN_WARNING_SEC = 30 * 60
PH_COOLDOWN_CRITICAL_SEC = 15 * 60

# ---- Salinity (ppt) ----
# Normal: 10–35; Warning: < 10 or > 35 and ≤ 109; Critical: < 5 or > 109
SAL_NORMAL_MIN = 10.0
SAL_NORMAL_MAX = 35.0
SAL_CRITICAL_HIGH_MIN = 109.0  # Critical: v > 109
SAL_CRITICAL_LOW_MAX = 5.0     # Critical: v < 5 ppt
SAL_WARNING_LOW_MAX = 10.0     # Warning when 5 <= v < 10
SAL_WARNING_HIGH_MIN = 35.0    # Warning when 35 < v <= 109
SAL_WARNING_HIGH_MAX = 109.0
SAL_COOLDOWN_WARNING_SEC = 30 * 60
SAL_COOLDOWN_CRITICAL_SEC = 15 * 60

# ---- TDS: read/transmit only; no SMS, no threshold classification, no relay ----

# THRESHOLDS for display (normal range = "Within Range")
THRESHOLDS = {
    "DO": {"min": 4.0, "max": None, "range_str": ">=4.0"},
    "pH": {"min": 7.5, "max": 8.5, "range_str": "7.5-8.5"},
    "TEMP": {"min": 26.0, "max": 30.0, "range_str": "26-30"},
    "SAL": {"min": 10.0, "max": 35.0, "range_str": "10-35"},
    "TDS": {"min": 0, "max": 9999, "range_str": "read only (no alerts)"},
}

NO_DATA_ALERT_COOLDOWN_SECONDS = 1200

# =====================================================
# PROPHET DAILY FORECAST (run from modified_ocr_live)
# =====================================================
PROPHET_SCRIPT_PATH = _MAIN_DIR / "prophet_server_raspi.py"
PROPHET_RUN_HOUR = 22   # 10 PM
PROPHET_RUN_MINUTE = 30  # 10:30 PM

# =====================================================
# TIMING
# =====================================================
READING_INTERVAL = 50
RECIPIENT_SYNC_INTERVAL = 10  # seconds between Firebase recipient syncs
STABILIZATION_FRAMES = 30
STABILIZATION_DELAY = 0.1
OCR_FRAME_COUNT = 25
OCR_FRAME_DELAY = 0.20
# Max number of frames per parameter that may be invalid ("?", "--", None); if more than this, param is invalid
MAX_INVALID_FRAMES_TOLERATED = 3
RESULT_DISPLAY_SECONDS = 1.0

# =====================================================
# IMAGE PROCESSING
# =====================================================
SEGMENT_THRESHOLD = 0.50
# Lower threshold for dimly lit display (retry when first decode fails)
ALT_SEGMENT_THRESHOLD = 0.35
DIGIT_ACTIVE_RATIO = 0.06
# Mean brightness (0-255) below this over digit ROIs = display off; do not trust OCR
# Lower value (e.g. 18) if "No data detected" appears while debug OCR sees the device
DISPLAY_OFF_BRIGHTNESS_THRESHOLD = 18

# =====================================================
# LOAD CALIBRATED DIGIT BOXES
# =====================================================
with open(SETUP_FILE, "rb") as _f:
    setup = pickle.load(_f)
