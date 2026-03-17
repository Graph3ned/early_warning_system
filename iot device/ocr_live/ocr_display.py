"""
Draw overlay on camera frame: preview (idle) and result (post-reading) views.
Digit boxes are calibrated for 1280x720; scale to actual frame size so they always fit.
"""

import cv2
import time

from ocr_config import PARAMETERS, THRESHOLDS, READING_INTERVAL, RESULT_DISPLAY_SECONDS

# Resolution used for digit box calibration; must match ocr_camera and digit_annotation.
CALIB_WIDTH, CALIB_HEIGHT = 1280, 720
from ocr_engine import (
    check_threshold,
    extract_numeric_value,
    conductivity_to_tds,
    conductivity_to_salinity,
)


def _draw_digit_boxes(overlay, setup):
    """Draw calibrated digit boxes on overlay (same as debug_ocr). Scale from CALIB to actual size."""
    h, w = overlay.shape[:2]
    sx = w / CALIB_WIDTH
    sy = h / CALIB_HEIGHT
    box_color_default = (0, 255, 255)
    for p in PARAMETERS:
        for i, (x1, y1, x2, y2) in enumerate(setup[p]["digits"]):
            color = (255, 255, 0) if (p == "CON" or p == "pH") and i == 0 and len(setup[p]["digits"]) == 4 else box_color_default
            pt1 = (int(x1 * sx), int(y1 * sy))
            pt2 = (int(x2 * sx), int(y2 * sy))
            cv2.rectangle(overlay, pt1, pt2, color, 2)


def draw_preview_overlay(overlay, display_results, last_ec_mScm, camera_on, should_take_reading, time_since_last_reading, setup=None):
    font = cv2.FONT_HERSHEY_SIMPLEX
    if setup is not None and camera_on:
        _draw_digit_boxes(overlay, setup)
    y_pos = 40
    line_height = 50
    all_empty = all(display_results.get(p) == "--" or not display_results.get(p) for p in PARAMETERS)
    tds = conductivity_to_tds(last_ec_mScm)
    temp_C = extract_numeric_value(display_results.get("TEMP")) if display_results else None
    sal = conductivity_to_salinity(last_ec_mScm)
    if all_empty:
        cv2.putText(overlay, "No data detected (device may be off)", (40, y_pos), font, 0.9, (0, 0, 255), 2)
        y_pos += line_height
        cv2.putText(overlay, "pH: --  TEMP: --  DO: --  EC: --", (40, y_pos), font, 0.7, (128, 128, 128), 2)
    else:
        # When camera on use white for text (readable on green LED); when off use original colors
        text_color = (255, 255, 255) if camera_on else None
        def _color(c):
            return text_color if camera_on and text_color else c
        if display_results.get("pH") and display_results["pH"] != "--":
            v = extract_numeric_value(display_results["pH"])
            if v is not None:
                status, color = check_threshold("pH", v)
                if status:
                    cv2.putText(overlay, "pH: " + str(display_results["pH"]) + " (Range: " + THRESHOLDS["pH"]["range_str"] + ") [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                    y_pos += line_height
        if display_results.get("TEMP") and display_results["TEMP"] != "--":
            v = extract_numeric_value(display_results["TEMP"])
            if v is not None:
                status, color = check_threshold("TEMP", v)
                if status:
                    cv2.putText(overlay, "TEMP: " + str(display_results["TEMP"]) + "C (Range: " + THRESHOLDS["TEMP"]["range_str"] + "C) [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                    y_pos += line_height
        if display_results.get("DO") and display_results["DO"] != "--":
            v = extract_numeric_value(display_results["DO"])
            if v is not None:
                status, color = check_threshold("DO", v)
                if status:
                    cv2.putText(overlay, "DO: " + str(display_results["DO"]) + " mg/L (Min: " + THRESHOLDS["DO"]["range_str"] + " mg/L) [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                    y_pos += line_height
        if sal is not None:
            status, color = check_threshold("SAL", sal)
            if status:
                cv2.putText(overlay, "SAL: " + str(sal) + " ppt (Range: " + THRESHOLDS["SAL"]["range_str"] + ") [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                y_pos += line_height
        if tds is not None:
            status, color = check_threshold("TDS", tds)
            if status:
                cv2.putText(overlay, "TDS: " + str(tds) + " ppt (Range: " + THRESHOLDS["TDS"]["range_str"] + ") [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                y_pos += line_height
        if display_results.get("CON") and display_results["CON"] != "--":
            ec_color = (255, 255, 255) if camera_on else (0, 0, 255)
            cv2.putText(overlay, "EC: " + str(display_results["CON"]), (40, y_pos), font, 0.8, ec_color, 2)
            y_pos += line_height
    if camera_on:
        camera_status, camera_color = "Camera: ON", (255, 0, 0)
    else:
        camera_status, camera_color = "Camera: OFF (saving power)", (0, 165, 255)
    cv2.putText(overlay, camera_status, (40, y_pos), font, 0.7, camera_color, 2)
    y_pos += 30
    if should_take_reading and camera_on:
        status_msg, status_color = "Taking reading now...", (255, 255, 255)
    elif should_take_reading and not camera_on:
        status_msg, status_color = "Initializing camera...", (0, 255, 255)
    else:
        tr = READING_INTERVAL - time_since_last_reading
        status_msg = "Next reading in: %02d:%02d" % (int(tr // 60), int(tr % 60))
        status_color = (0, 255, 255)
    cv2.putText(overlay, status_msg, (40, y_pos), font, 0.8, status_color, 2)


def draw_result_overlay(overlay, last_results, last_ec_mScm, setup, display_start_time, camera_on=True):
    font = cv2.FONT_HERSHEY_SIMPLEX
    _draw_digit_boxes(overlay, setup)
    # When camera on use white (readable on green LED); when off use original colors
    text_color = (255, 255, 255) if camera_on else None
    def _color(c):
        return text_color if camera_on and text_color else c
    y_pos = 40
    line_height = 50
    if last_results.get("pH"):
        v = extract_numeric_value(last_results["pH"])
        if v is not None:
            status, color = check_threshold("pH", v)
            if status:
                cv2.putText(overlay, "pH: " + str(last_results["pH"]) + " (Range: " + THRESHOLDS["pH"]["range_str"] + ") [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                y_pos += line_height
    if last_results.get("TEMP"):
        v = extract_numeric_value(last_results["TEMP"])
        if v is not None:
            status, color = check_threshold("TEMP", v)
            if status:
                cv2.putText(overlay, "TEMP: " + str(last_results["TEMP"]) + "C (Range: " + THRESHOLDS["TEMP"]["range_str"] + "C) [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                y_pos += line_height
    if last_results.get("DO"):
        v = extract_numeric_value(last_results["DO"])
        if v is not None:
            status, color = check_threshold("DO", v)
            if status:
                cv2.putText(overlay, "DO: " + str(last_results["DO"]) + " mg/L (Min: " + THRESHOLDS["DO"]["range_str"] + " mg/L) [" + status + "]", (40, y_pos), font, 0.8, _color(color), 2)
                y_pos += line_height
    if last_results.get("CON"):
        ec_color = (255, 255, 255) if camera_on else (0, 255, 0)
        cv2.putText(overlay, "EC: " + str(last_results["CON"]), (40, y_pos), font, 0.8, ec_color, 2)
        y_pos += line_height
    tds_d = conductivity_to_tds(last_ec_mScm)
    temp_d = extract_numeric_value(last_results.get("TEMP")) if last_results else None
    sal_d = conductivity_to_salinity(last_ec_mScm)
    if tds_d:
        tds_color = (255, 255, 255) if camera_on else (0, 255, 0)
        cv2.putText(overlay, "TDS: " + str(tds_d) + " ppt", (40, 260), font, 1.2, tds_color, 3)
    if sal_d:
        sal_color = (255, 255, 255) if camera_on else (0, 255, 0)
        cv2.putText(overlay, "SAL: " + str(sal_d) + " ppt", (40, 310), font, 1.2, sal_color, 3)
    time_left = int(RESULT_DISPLAY_SECONDS - (time.time() - display_start_time))
    cv2.putText(overlay, "Camera off in: %ds" % time_left, (40, 360), font, 0.8, (0, 255, 255), 2)
