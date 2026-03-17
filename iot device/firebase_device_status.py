"""
Write Raspberry Pi device and reading status to Firebase for the mobile app.

The app reads device_status to display:
  - Reading status: ok, no_data, or invalid_readings.
  - ESP8266 connection: true or false (updated on init and on each relay call).
  - Pi CPU temperature (C) and a short status message when reading_status is ok.
  - Invalid parameters list when status is invalid_readings.

Firebase path: device_status (single object, overwritten on each update).
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import firebase_admin
from firebase_admin import credentials, db

_root = Path(__file__).resolve().parent
FIREBASE_KEY_PATH = __import__("os").environ.get("FIREBASE_KEY_PATH", str(_root / "firebase_key.json"))
DATABASE_URL = "https://early-waring-system-default-rtdb.asia-southeast1.firebasedatabase.app/"
DEVICE_STATUS_PATH = "device_status"

# Last status sent (so periodic update can resend with fresh ESP + Pi temp)
_last_reading_status = "ok"
_last_invalid_params = None  # type: Optional[List[str]]
_last_message = None  # type: Optional[str]

# Raspberry Pi CPU temperature (millidegrees C)
_PI_THERMAL_PATH = Path("/sys/class/thermal/thermal_zone0/temp")


def get_pi_temperature_celsius() -> Optional[float]:
    """Read Pi CPU temperature in °C. Returns None if not on Pi or read fails."""
    try:
        if _PI_THERMAL_PATH.exists():
            raw = _PI_THERMAL_PATH.read_text().strip()
            if raw.isdigit():
                return round(int(raw) / 1000.0, 1)
    except Exception:
        pass
    return None


def get_pi_temperature_status(temp_celsius: float) -> str:
    """
    Return a short status message for Pi CPU temperature for the app.
    Ranges: idle 35–50°C, normal 50–70°C, heavy 70–80°C, high 80–85°C, critical 85°C+.
    """
    if temp_celsius >= 85:
        return "Critical (85 C+): CPU throttling to prevent damage"
    if temp_celsius >= 80:
        return "High (80-85 C): Throttling may start"
    if temp_celsius >= 70:
        return "Heavy load (70–80°C)"
    if temp_celsius >= 50:
        return "Normal workload (50–70°C)"
    if temp_celsius >= 35:
        return "Idle / light use (35–50°C)"
    return "Cool (<35°C)"


def _init_firebase() -> bool:
    if not firebase_admin._apps:
        if not Path(FIREBASE_KEY_PATH).exists():
            return False
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
    return True


def write_device_status(
    reading_status: str,
    invalid_params: Optional[List[str]] = None,
    message: Optional[str] = None,
    pi_temperature_celsius: Optional[float] = None,
    use_relay_state_only: bool = False,
) -> bool:
    """
    Write Pi device status to Firebase at device_status.
    When use_relay_state_only=False (default): runs ESP reachability check and sends that result
    (so unplugging the ESP is detected even if relay/GSM were not called).
    When use_relay_state_only=True: sends relay_control.esp_connected only (no check).
    """
    global _last_reading_status, _last_invalid_params, _last_message
    _last_reading_status = reading_status
    _last_invalid_params = invalid_params
    _last_message = message

    # Use the same relay_control module the main thread uses (avoid ocr_live.relay_control as second copy).
    _relay_module = None
    try:
        import sys
        _relay_module = sys.modules.get("relay_control")
        if _relay_module is None:
            import ocr_live.relay_control as _relay_module
        if use_relay_state_only:
            # Periodic update: use relay state only (set by init/activate/deactivate or last check).
            esp_connected = _relay_module.esp_connected
        else:
            # Run actual ESP reachability check and trust the result (so unplug is detected).
            from esp8266 import check_esp_reachable
            client = _relay_module.get_esp_client()
            check_ok = check_esp_reachable(client, silent=True)
            esp_connected = check_ok
            _relay_module.set_esp_connected(esp_connected)
    except Exception:
        esp_connected = False
        try:
            if _relay_module is not None:
                _relay_module.set_esp_connected(False)
        except Exception:
            pass

    if not _init_firebase():
        return False
    try:
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now()
        payload = {
            "reading_status": reading_status,
            "last_updated_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_updated_local": now_local.strftime("%Y-%m-%dT%H:%M:%S"),
            "esp_connected": esp_connected,
        }
        if invalid_params is not None:
            payload["invalid_params"] = invalid_params
        temp = pi_temperature_celsius if pi_temperature_celsius is not None else get_pi_temperature_celsius()
        if temp is not None:
            payload["pi_temperature_celsius"] = temp
        # message: from caller (no_data / invalid_readings) or, when ok, Pi temperature status
        if message is not None:
            payload["message"] = message
        elif temp is not None:
            payload["message"] = get_pi_temperature_status(temp)

        print(f"[device_status] Pushing to Firebase: {payload}")
        ref = db.reference(DEVICE_STATUS_PATH)
        ref.set(payload)
        return True
    except Exception:
        return False


def refresh_device_status() -> bool:
    """
    Re-write device_status to Firebase with last reading_status/invalid_params/message.
    ESP check runs inside write_device_status (silent). Optional helper for manual refresh.
    """
    return write_device_status(
        reading_status=_last_reading_status,
        invalid_params=_last_invalid_params,
        message=_last_message,
    )


def run_periodic_device_status_update() -> bool:
    """
    Write device_status to Firebase with last reading_status. Runs ESP reachability check
    so that unplugging the ESP is detected even when relay/GSM are not called.
    Call every READING_INTERVAL.
    """
    try:
        return write_device_status(
            reading_status=_last_reading_status,
            invalid_params=_last_invalid_params,
            message=_last_message,
            use_relay_state_only=False,
        )
    except Exception:
        return False
