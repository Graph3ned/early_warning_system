"""
YK-100 seven-segment OCR: digit decoding, value formatting, threshold checks, and unit conversions.
"""

import math
import re
import cv2
import numpy as np

from ocr_config import (
    PARAMETERS,
    THRESHOLDS,
    SEGMENT_THRESHOLD,
    ALT_SEGMENT_THRESHOLD,
    DIGIT_ACTIVE_RATIO,
    DISPLAY_OFF_BRIGHTNESS_THRESHOLD,
    setup,
)

# =====================================================
# TILT CORRECTION
# =====================================================

def correct_tilt(image, angle_deg, center=None):
    """
    Rotate image by angle_deg (counter-clockwise) to correct display tilt.
    If the LED appears tilted to the left, use a positive angle (e.g. 1.5–3.0).
    Returns image of same size (corners may be black for large angles).
    """
    if angle_deg == 0 or image is None or image.size == 0:
        return image
    h, w = image.shape[:2]
    if center is None:
        center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    out = cv2.warpAffine(image, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return out


# =====================================================
# SEVEN-SEGMENT MAP
# =====================================================

# Only 0-9 are valid. Any other decoded value (e.g. letter from misread segment) → invalid ("?").
VALID_DIGITS = set("0123456789")

SEGMENT_MAP = {
    (1,1,1,1,1,1,0): 0,
    (0,1,1,0,0,0,0): 1,
    (1,1,0,1,1,0,1): 2,
    (1,1,1,1,0,0,1): 3,
    (0,1,1,0,0,1,1): 4,
    (1,0,1,1,0,1,1): 5,
    (1,0,1,1,1,1,1): 6,
    (1,1,1,0,0,0,0): 7,
    (1,1,1,1,1,1,1): 8,
    (1,1,1,1,0,1,1): 9,
}


def segment_states(bin_img, threshold=None):
    if threshold is None:
        threshold = SEGMENT_THRESHOLD
    h, w = bin_img.shape
    segments = [
        bin_img[0:int(h*0.2), int(w*0.2):int(w*0.8)],
        bin_img[int(h*0.2):int(h*0.5), int(w*0.7):w],
        bin_img[int(h*0.5):int(h*0.8), int(w*0.7):w],
        bin_img[int(h*0.8):h, int(w*0.2):int(w*0.8)],
        bin_img[int(h*0.5):int(h*0.8), 0:int(w*0.3)],
        bin_img[int(h*0.2):int(h*0.5), 0:int(w*0.3)],
        bin_img[int(h*0.4):int(h*0.6), int(w*0.2):int(w*0.8)],
    ]
    return tuple(1 if cv2.countNonZero(s) > threshold * s.size else 0 for s in segments)


def is_digit_active(bin_img, ratio=None):
    if ratio is None:
        ratio = DIGIT_ACTIVE_RATIO
    black = bin_img.size - cv2.countNonZero(bin_img)
    return black > ratio * bin_img.size


def decode_two_segment(bin_img, threshold=None):
    if threshold is None:
        threshold = SEGMENT_THRESHOLD
    h, w = bin_img.shape
    top_seg = bin_img[0:int(h*0.5), int(w*0.2):int(w*0.8)]
    bottom_seg = bin_img[int(h*0.5):h, int(w*0.2):int(w*0.8)]
    top_ratio = cv2.countNonZero(top_seg) / top_seg.size
    bottom_ratio = cv2.countNonZero(bottom_seg) / bottom_seg.size
    top_on = 1 if top_ratio > threshold else 0
    bottom_on = 1 if bottom_ratio > threshold else 0
    if top_on == 1 and bottom_on == 0:
        return 1
    elif top_on == 0 and bottom_on == 1:
        return ("?", "2seg:bottom_only")
    elif top_on == 1 and bottom_on == 1:
        if top_ratio > bottom_ratio * 1.2:
            return 1
        elif bottom_ratio > top_ratio * 1.2:
            return ("?", "2seg:bottom_dominates")
        return 1
    return ("?", "2seg:both_off")


def decode_seven_segment(bin_img, threshold=None):
    if threshold is None:
        threshold = SEGMENT_THRESHOLD
    h, w = bin_img.shape
    segments = [
        bin_img[0:int(h*0.2), int(w*0.2):int(w*0.8)],
        bin_img[int(h*0.2):int(h*0.5), int(w*0.7):w],
        bin_img[int(h*0.5):int(h*0.8), int(w*0.7):w],
        bin_img[int(h*0.8):h, int(w*0.2):int(w*0.8)],
        bin_img[int(h*0.5):int(h*0.8), 0:int(w*0.3)],
        bin_img[int(h*0.2):int(h*0.5), 0:int(w*0.3)],
        bin_img[int(h*0.4):int(h*0.6), int(w*0.2):int(w*0.8)],
    ]
    on = [1 if cv2.countNonZero(s) > threshold*s.size else 0 for s in segments]
    pattern = tuple(on)
    if pattern in SEGMENT_MAP:
        return SEGMENT_MAP[pattern]
    best_match, min_distance = None, float('inf')
    for known_pattern, digit in SEGMENT_MAP.items():
        distance = sum(1 for a, b in zip(pattern, known_pattern) if a != b)
        if distance < min_distance:
            min_distance, best_match = distance, digit
    # Allow at most 1 difference (missing or extra segment)
    if min_distance <= 1 and best_match is not None:
        return best_match
    # Dimly lit: retry with lower threshold
    if threshold == SEGMENT_THRESHOLD:
        return decode_seven_segment(bin_img, threshold=ALT_SEGMENT_THRESHOLD)
    return ("?", "7seg:no_match")


def sanitize_decoded_digit(decoded):
    """
    Accept only digits (0-9) or "?". Any other value (e.g. letter from misread segment
    like f/g/c) is treated as invalid → "?" so the reading is marked invalid, not corrected.
    """
    if decoded == "?":
        return "?"
    s = str(decoded).strip()
    if s in VALID_DIGITS:
        return s
    return "?"


def apply_decimal(param, raw):
    if not raw:
        return raw
    n = len(raw)
    if param == "pH":
        if n == 3:
            return raw[0] + "." + raw[1:]
        if n == 4:
            return raw[:2] + "." + raw[2:]
    if param == "TEMP" and n == 3:
        return raw[:2] + "." + raw[2]
    if param == "DO":
        if n == 3:
            return raw[0] + "." + raw[1:]
        if n == 4:
            return raw[:2] + "." + raw[2:]
    if param == "CON":
        if n == 4:
            return raw[:2] + "." + raw[2:]
        if n == 3:
            return raw
    return raw


def check_threshold(param, value):
    if param not in THRESHOLDS or value is None:
        return None, None
    try:
        num_value = float(value)
    except (ValueError, TypeError):
        return None, None
    t = THRESHOLDS[param]
    min_val, max_val = t["min"], t["max"]
    if max_val is None:
        return ("Below Range", (0, 0, 255)) if num_value < min_val else ("Within Range", (0, 255, 0))
    if num_value < min_val:
        return "Below Range", (0, 0, 255)
    if num_value > max_val:
        return "Above Range", (0, 165, 255)
    return "Within Range", (0, 255, 0)


def extract_numeric_value(value_str):
    if not value_str or value_str == "--" or "?" in str(value_str):
        return None
    try:
        cleaned = str(value_str).strip()
        for unit in ["mg/L", "uS", "µS", "mS", "C", "°C", "ppt"]:
            cleaned = cleaned.replace(unit, "").strip()
        match = re.search(r'[\d.]+', cleaned)
        if match:
            return float(match.group())
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def conductivity_to_tds(ec_mScm):
    """TDS (ppt) = 0.7 * EC_mScm; EC in mS/cm (as read from OCR)."""
    if ec_mScm is None:
        return None
    return round(0.7 * ec_mScm, 3)


def conductivity_to_salinity(ec_mScm):
    """
    Convert EC (mS/cm) to salinity in ppt. Linear formula: 0.657973 * EC_mScm - 2.245991.
    """
    if ec_mScm is None:
        return None
    sal = 0.657973 * ec_mScm - 2.245991
    return round(float(sal), 2)


# =====================================================
# DO SALINITY COMPENSATION (USGS WQ.2011.03 — Weiss 1970)
# =====================================================
def salinity_factor_weiss(temp_C: float, salinity_ppt: float) -> float:
    """
    Weiss (1970) Eq. 3: F_S = exp{ S * [ -0.033096 + 0.014259(T/100) - 0.0017000(T/100)^2 ] }
    S = salinity ppt, T = temperature Kelvin. Returns factor to multiply raw DO (mg/L) for salinity compensation.
    """
    T = temp_C + 273.15
    T100 = T / 100.0
    return math.exp(
        salinity_ppt * (-0.033096 + 0.014259 * T100 - 0.0017000 * (T100**2))
    )


def do_salt_compensated_mgl(do_mgl_raw: float, Fs: float) -> float:
    """Apply salinity factor to raw DO (mg/L) to get salinity-compensated DO (mg/L)."""
    return round(do_mgl_raw * Fs, 2)


def _display_mean_brightness(gray, setup_dict):
    """Mean brightness over all digit ROIs. Low value = display likely off."""
    if gray is None or not setup_dict:
        return 0.0
    pixels = []
    for p in PARAMETERS:
        if p not in setup_dict:
            continue
        info = setup_dict[p]
        for (x1, y1, x2, y2) in info.get("digits", []):
            roi = gray[y1:y2, x1:x2]
            if roi.size:
                pixels.append(np.mean(roi))
    return float(np.mean(pixels)) if pixels else 0.0


def run_ocr(setup_dict, gray, last_valid, last_ec_mScm):
    """
    Run OCR on a gray frame. Returns (results, updated_last_valid, updated_last_ec_mScm, invalid_reasons).
    EC is kept in mS/cm (as read from display); no conversion to µS/cm.
    invalid_reasons: dict param -> list of (digit_index, reason_str) for each "?" digit.
    If display is off (mean brightness below threshold), returns all '--' and does not update last_valid.
    """
    results = {}
    last_valid = dict(last_valid) if last_valid else {p: None for p in PARAMETERS}
    ec_mScm = last_ec_mScm
    invalid_reasons = {}

    mean_brightness = _display_mean_brightness(gray, setup_dict)
    if mean_brightness < DISPLAY_OFF_BRIGHTNESS_THRESHOLD:
        for p in PARAMETERS:
            results[p] = "--"
        return results, last_valid, last_ec_mScm, invalid_reasons

    for p in PARAMETERS:
        info = setup_dict[p]
        digits = []
        original_valid_digit_count = 0
        invalid_reasons[p] = []

        for i, (x1, y1, x2, y2) in enumerate(info["digits"]):
            roi = gray[y1:y2, x1:x2]
            adjusted = np.clip(info["alpha"] * roi + info["beta"], 0, 255).astype(np.uint8)
            bin_img = cv2.adaptiveThreshold(
                adjusted, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,
                info["blockSize"] | 1, info["offset"],
            )
            if (p == "CON" or p == "pH" or p == "DO") and i == 0 and len(info["digits"]) == 4:
                decoded = decode_two_segment(bin_img)
            else:
                decoded = decode_seven_segment(bin_img)

            # Unpack (?, reason) from decode when invalid
            if isinstance(decoded, tuple):
                decoded, reason = decoded
                invalid_reasons[p].append((i, reason))
            else:
                reason = None

            # Two-segment (CON/pH/DO first digit when 4 digits): trust decoded "1"; only use activity check when decoded is "?"
            is_two_segment = (p == "CON" or p == "pH" or p == "DO") and i == 0 and len(info["digits"]) == 4
            if is_two_segment and decoded == 1:
                digits.append("1")
                original_valid_digit_count += 1
                continue
            # pH first digit when 3 digits: no two-segment "1"; use seven-segment decode and don't force "?" from activity check (same idea as CON)
            is_ph_first_3 = p == "pH" and i == 0 and len(info["digits"]) == 3
            if is_ph_first_3:
                sanitized = sanitize_decoded_digit(decoded)
                digits.append(sanitized)
                if sanitized == "?" and reason is None:
                    invalid_reasons[p].append((i, "sanitized_non_digit"))
                if sanitized != "?":
                    original_valid_digit_count += 1
                continue
            if not is_two_segment and not is_digit_active(bin_img):
                digits.append("?")
                if not any(r[0] == i for r in invalid_reasons[p]):
                    invalid_reasons[p].append((i, "digit_inactive"))
                continue
            if is_two_segment and not is_digit_active(bin_img):
                digits.append("?")
                if not any(r[0] == i for r in invalid_reasons[p]):
                    invalid_reasons[p].append((i, "digit_inactive"))
                continue
            sanitized = sanitize_decoded_digit(decoded)
            digits.append(sanitized)
            if sanitized == "?" and reason is None:
                invalid_reasons[p].append((i, "sanitized_non_digit"))
            if sanitized != "?":
                original_valid_digit_count += 1
                # remove reason if we had one (shouldn't happen for valid digit)
                invalid_reasons[p] = [(di, r) for di, r in invalid_reasons[p] if di != i]

        raw = "".join(digits)
        expected_digits = len(info["digits"])
        has_valid_digit = any(d != "?" for d in digits)

        if not has_valid_digit:
            raw = None
        elif "?" in raw:
            if p == "CON" and expected_digits == 4:
                # Only zero-pad when all "?" are leading (known digits form a contiguous suffix).
                # e.g. "??32" → "0032"; "?3?2" has "?" in middle → invalid, keep "?3?2".
                valid_indices = [i for i in range(4) if digits[i] != "?"]
                if not valid_indices:
                    raw = "?" * 4
                elif valid_indices == list(range(4 - len(valid_indices), 4)):
                    suffix_digits = [digits[i] for i in valid_indices]
                    if len(valid_indices) == 3:
                        raw = "".join(suffix_digits)  # 575 → µS
                    else:
                        raw = ("0" * (4 - len(valid_indices))) + "".join(suffix_digits)
                    if "?" not in raw:
                        last_valid[p] = raw
                else:
                    raw = "".join(digits)  # keep "?" in place → invalid reading
            elif p == "pH" and expected_digits == 4:
                # Same as CON: if "?" only in leading positions (e.g. first digit inactive), set to "0" so "?621" → 06.21.
                # If "?" in middle, keep invalid.
                valid_indices = [i for i in range(4) if digits[i] != "?"]
                if not valid_indices:
                    raw = "?" * 4
                elif valid_indices == list(range(4 - len(valid_indices), 4)):
                    suffix_digits = [digits[i] for i in valid_indices]
                    raw = ("0" * (4 - len(valid_indices))) + "".join(suffix_digits)
                    if "?" not in raw:
                        last_valid[p] = raw
                else:
                    raw = "".join(digits)  # "?" in middle → invalid
            elif p == "DO" and expected_digits == 4:
                # Same as pH: if "?" only in leading positions, zero-pad so "?621" → 06.21 (mg/L).
                valid_indices = [i for i in range(4) if digits[i] != "?"]
                if not valid_indices:
                    raw = "?" * 4
                elif valid_indices == list(range(4 - len(valid_indices), 4)):
                    suffix_digits = [digits[i] for i in valid_indices]
                    raw = ("0" * (4 - len(valid_indices))) + "".join(suffix_digits)
                    if "?" not in raw:
                        last_valid[p] = raw
                else:
                    raw = "".join(digits)
            else:
                if len(digits) < expected_digits:
                    valid_digits = [d for d in digits if d != "?"]
                    raw = ("?" * (expected_digits - len(valid_digits)) + "".join(valid_digits)) if valid_digits else "?" * expected_digits
                if "?" not in raw:
                    last_valid[p] = raw
        else:
            last_valid[p] = raw
            if len(raw) < expected_digits:
                raw = "?" * (expected_digits - len(raw)) + raw

        # Never use last_valid as current reading; only output what we read this frame.
        formatted = None
        if p == "CON" and raw:
            if "?" in raw:
                # "?" in middle or anywhere → invalid reading; don't guess or use ec_mScm
                results["CON"] = "?"
            else:
                # Conductivity formatting:
                # - 4 digits: XX.XX mS
                # - 3 digits: XX.X mS (decimal after 2nd digit), e.g. "503" -> "50.3 mS"
                numeric_part = raw.replace("?", "")
                is_4_digit = len(numeric_part) == 4
                is_3_digit = len(numeric_part) == 3
                treat_as_mS = is_4_digit or is_3_digit

                if treat_as_mS:
                    if len(numeric_part) == 4:
                        formatted = numeric_part[:2] + "." + numeric_part[2:]
                    elif len(numeric_part) == 3:
                        formatted = numeric_part[:2] + "." + numeric_part[2]
                    else:
                        formatted = numeric_part
                else:
                    formatted = numeric_part
                if formatted:
                    results["CON"] = f"{formatted} mS" if treat_as_mS else f"{formatted} uS"
                    if numeric_part:
                        try:
                            if treat_as_mS:
                                ec_mScm = float(formatted)
                            else:
                                ec_mScm = int(numeric_part) / 1000.0
                        except (ValueError, TypeError):
                            pass
                else:
                    results["CON"] = "?"
        else:
            formatted = apply_decimal(p, raw) if raw else None
            if raw is None:
                results[p] = "--"
            elif "?" in raw:
                results[p] = formatted or raw or "?"
            else:
                results[p] = formatted

    return results, last_valid, ec_mScm, invalid_reasons
