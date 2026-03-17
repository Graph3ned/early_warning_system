"""
Marine fish cage (Bangus) early warning: threshold classification, SMS message text, cooldowns.
Non-blocking; all timing is checked by the caller using last_alert_time.
"""

from ocr_config import (
    DO_NORMAL_MIN,
    DO_WARNING_SMS_MAX,
    DO_CRITICAL_MAX,
    DO_COOLDOWN_WARNING_SEC,
    DO_COOLDOWN_CRITICAL_SEC,
    TEMP_NORMAL_MIN,
    TEMP_NORMAL_MAX,
    TEMP_CRITICAL_LOW_MAX,
    TEMP_CRITICAL_HIGH_MIN,
    TEMP_COOLDOWN_WARNING_SEC,
    TEMP_COOLDOWN_CRITICAL_SEC,
    SAL_NORMAL_MIN,
    SAL_NORMAL_MAX,
    SAL_CRITICAL_LOW_MAX,
    SAL_CRITICAL_HIGH_MIN,
    SAL_COOLDOWN_WARNING_SEC,
    SAL_COOLDOWN_CRITICAL_SEC,
    PH_NORMAL_MIN,
    PH_NORMAL_MAX,
    PH_CRITICAL_LOW_MAX,
    PH_CRITICAL_HIGH_MIN,
    PH_COOLDOWN_WARNING_SEC,
    PH_COOLDOWN_CRITICAL_SEC,
)


def get_level_do(value):
    """Return 'normal', 'warning', or 'critical'. Normal ≥4, Warning 2.5–<4, Critical < 2.5 mg/L."""
    if value is None:
        return None
    v = float(value)
    if v >= DO_NORMAL_MIN:
        return "normal"
    if v < DO_CRITICAL_MAX:     # Critical: < 2.5 (2.5 is warning)
        return "critical"
    return "warning"             # Warning: 2.5 ≤ v < 4


def get_level_temp(value):
    """Normal 26–30 °C, Warning 23–<26 or >30–35, Critical < 23 or > 35."""
    if value is None:
        return None
    v = float(value)
    if TEMP_NORMAL_MIN <= v <= TEMP_NORMAL_MAX:
        return "normal"
    if v < TEMP_CRITICAL_LOW_MAX or v > TEMP_CRITICAL_HIGH_MIN:
        return "critical"
    return "warning"


def get_level_sal(value):
    """Normal 10–35 ppt, Warning 5–<10 or > 35 and ≤ 109, Critical < 5 or > 109."""
    if value is None:
        return None
    v = float(value)
    if SAL_NORMAL_MIN <= v <= SAL_NORMAL_MAX:
        return "normal"
    if v < SAL_CRITICAL_LOW_MAX or v > SAL_CRITICAL_HIGH_MIN:  # Critical < 5 or > 109
        return "critical"
    return "warning"


def get_level_ph(value):
    """Normal 7.5–8.5, Warning 6–<7.5 or 8.5–9.5, Critical < 6 or > 9.5."""
    if value is None:
        return None
    v = float(value)
    if PH_NORMAL_MIN <= v <= PH_NORMAL_MAX:
        return "normal"
    if v < PH_CRITICAL_LOW_MAX or v > PH_CRITICAL_HIGH_MIN:
        return "critical"
    return "warning"


def should_send_sms_do(value):
    """Return (level,) if we should send SMS, else (None,). Send SMS only when DO is warning or critical (v < 4.0)."""
    level = get_level_do(value)
    if level is None:
        return (None,)
    if level == "critical":
        return ("critical",)
    if level == "warning":
        return ("warning",)
    return (None,)  # normal (v >= 4.0): no SMS


def should_send_sms_temp(value):
    """Send SMS for Warning and Critical when outside normal range (temp < 26 or temp > 30)."""
    if value is None:
        return (None,)
    level = get_level_temp(value)
    if level is None:
        return (None,)
    v = float(value)
    if v < TEMP_NORMAL_MIN or v > TEMP_NORMAL_MAX:
        return (level,)
    return (None,)


def should_send_sms_sal(value):
    """Send SMS for Warning and Critical when outside normal range (salinity < 10 or > 35)."""
    if value is None:
        return (None,)
    level = get_level_sal(value)
    if level is None:
        return (None,)
    v = float(value)
    if v < SAL_NORMAL_MIN or v > SAL_NORMAL_MAX:
        return (level,)
    return (None,)


def should_send_sms_ph(value):
    """Send SMS for Warning and Critical when outside normal range (pH < 7.5 or > 8.5)."""
    if value is None:
        return (None,)
    level = get_level_ph(value)
    if level is None:
        return (None,)
    v = float(value)
    if v < PH_NORMAL_MIN or v > PH_NORMAL_MAX:
        return (level,)
    return (None,)


def get_cooldown_seconds(param, level):
    """Cooldown duration for (param, level)."""
    if level == "critical":
        return {
            "DO": DO_COOLDOWN_CRITICAL_SEC,
            "TEMP": TEMP_COOLDOWN_CRITICAL_SEC,
            "SAL": SAL_COOLDOWN_CRITICAL_SEC,
            "pH": PH_COOLDOWN_CRITICAL_SEC,
        }.get(param, 900)
    return {
        "DO": DO_COOLDOWN_WARNING_SEC,
        "TEMP": TEMP_COOLDOWN_WARNING_SEC,
        "SAL": SAL_COOLDOWN_WARNING_SEC,
        "pH": PH_COOLDOWN_WARNING_SEC,
    }.get(param, 1800)


def get_sms_message_do(value, level):
    if level == "critical":
        return (
            f"CRITICAL ALERT: Dissolved Oxygen is {value} mg/L (BFAR optimum >=4 mg/L). "
            "May cause severe stress to milkfish. Immediate assessment recommended."
        )
    return (
        f"ALERT: Dissolved Oxygen is {value} mg/L (BFAR optimum >=4 mg/L for bangus cage). "
        "Monitoring advised."
    )


def get_sms_message_temp(value, level):
    # Use " C" instead of degree symbol so SMS displays correctly on all handsets.
    if level == "critical":
        return (
            f"CRITICAL ALERT: Sea water temperature is {value} C (BFAR optimum 26-30 C). "
            "May cause severe stress to milkfish. Immediate assessment recommended."
        )
    return (
        f"ALERT: Sea water temperature is {value} C (BFAR optimum 26-30 C for bangus cage). "
        "Monitoring advised."
    )


def get_sms_message_sal(value, level):
    if level == "critical":
        return (
            f"CRITICAL ALERT: Sea water salinity is {value} ppt (BFAR optimum 10-35 ppt). "
            "May cause osmotic stress to milkfish. Immediate assessment recommended."
        )
    return (
        f"ALERT: Sea water salinity is {value} ppt (BFAR optimum 10-35 ppt for bangus cage). "
        "Monitoring advised."
    )


def get_sms_message_ph(value, level):
    if level == "critical":
        return (
            f"CRITICAL ALERT: Sea water pH is {value} (BFAR optimum 7.5-8.5). "
            "May cause physiological stress to milkfish. Immediate assessment recommended."
        )
    return (
        f"ALERT: Sea water pH is {value} (BFAR optimum 7.5-8.5 for bangus cage). "
        "Monitoring advised."
    )


def get_sms_message(param, value, level):
    """Return the SMS body for (param, value, level)."""
    if param == "DO":
        return get_sms_message_do(value, level)
    if param == "TEMP":
        return get_sms_message_temp(value, level)
    if param == "SAL":
        return get_sms_message_sal(value, level)
    if param == "pH":
        return get_sms_message_ph(value, level)
    return None
