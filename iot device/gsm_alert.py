"""
SMS alert delivery via GSM module on ESP8266.

The GSM module is attached to the ESP8266 and controlled over WiFi HTTP. This module provides:
  1. send_no_data_alert(phone_numbers) — device display off or blank (static numbers).
  2. send_invalid_readings_alert(phone_numbers, invalid_params) — invalid or incomplete readings (static numbers).
  3. send_water_quality_alert / send_alert_to_all_recipients — threshold violations (recipients from database).
"""

from recipient_storage import get_active_phone_numbers
import threading
import time

from esp8266 import ESP8266_IP, ESP8266_PORT

# =====================================================
# SINGLE SEND AT A TIME
# =====================================================
# Only one alert-send batch can run at a time (avoids overlapping threads when
# reading cycle re-triggers alert before the first batch finishes).
_alert_send_lock = threading.Lock()

# =====================================================
# PER-RECIPIENT, PER-COOLDOWN-KEY
# =====================================================
# Each (recipient, cooldown_key) gets at most one alert per this many seconds.
# Different parameters (e.g. DO vs Salinity/TDS) use different keys so one does not block the other.
RECIPIENT_COOLDOWN_SECONDS = 1800  # 30 minutes

# (phone_number, cooldown_key) -> last send timestamp
_last_alert_time_by_number = {}

def _recipients_past_cooldown(phone_numbers, cooldown_key="default", cooldown_seconds=None):
    """Return only numbers that are past cooldown for this cooldown_key."""
    now = time.time()
    sec = cooldown_seconds if cooldown_seconds is not None else RECIPIENT_COOLDOWN_SECONDS
    return [p for p in phone_numbers if (now - _last_alert_time_by_number.get((p, cooldown_key), 0)) >= sec]

# =====================================================
# GSM MODULE FACTORY
# =====================================================
def create_gsm_module():
    """
    Create GSM module instance via ESP8266.
    
    Returns:
        GSMViaESP8266 instance
    """
    try:
        from esp8266 import GSMViaESP8266, ESP8266Client
        client = ESP8266Client(ip_address=ESP8266_IP, port=ESP8266_PORT)
        return GSMViaESP8266(esp8266_client=client)
    except ImportError:
        print("[ERROR] ESP8266 client not available. Install requests: pip install requests")
        raise

# =====================================================
# ALERT FUNCTIONS
# =====================================================
def send_alert_to_static_numbers(phone_numbers, message, gsm_module=None):
    """
    Send alert SMS to a list of static phone numbers.
    
    Args:
        phone_numbers: List of phone number strings
        message: Alert message text
        gsm_module: GSMModule instance (optional, will create if not provided)
    
    Returns:
        dict: Results {
            'total': int,
            'success': int,
            'failed': int,
            'recipients': list of phone numbers
        }
    """
    if not _alert_send_lock.acquire(blocking=False):
        print("[INFO] Alert send already in progress; skipping this batch.")
        return {'total': 0, 'success': 0, 'failed': 0, 'recipients': list(phone_numbers) if phone_numbers else []}
    try:
        return _send_alert_to_static_numbers_impl(phone_numbers, message, gsm_module)
    finally:
        _alert_send_lock.release()


def _send_alert_to_static_numbers_impl(phone_numbers, message, gsm_module=None):
    """Implementation of send_alert_to_static_numbers (called with lock held)."""
    if not phone_numbers:
        print("[WARN] No phone numbers provided")
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'recipients': []
        }

    # Only send to numbers past their per-recipient cooldown for this alert type
    to_send = _recipients_past_cooldown(phone_numbers, cooldown_key="default")
    skipped = len(phone_numbers) - len(to_send)
    if skipped:
        print(f"[INFO] Skipping {skipped} recipient(s) still in cooldown")
    if not to_send:
        print("[INFO] No recipients past cooldown; skipping send")
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'recipients': phone_numbers
        }
    
    print(f"Sending alert to {len(to_send)} static recipient(s)...")
    
    # Initialize GSM module if not provided
    if gsm_module is None:
        gsm_module = create_gsm_module()
        if not gsm_module.connect():
            print("[ERROR] Failed to connect to GSM module")
            return {
                'total': len(to_send),
                'success': 0,
                'failed': len(to_send),
                'recipients': to_send
            }
        should_disconnect = True
    else:
        should_disconnect = False
    
    results = {
        'total': len(to_send),
        'success': 0,
        'failed': 0,
        'recipients': to_send
    }
    
    # Send SMS to each recipient (one at a time); record cooldown per number when send succeeds
    SMS_DELAY_BETWEEN_RECIPIENTS = 2.5  # seconds so modem can transmit before next
    for phone_number in to_send:
        if gsm_module.send_sms(phone_number, message):
            results['success'] += 1
            _last_alert_time_by_number[phone_number] = time.time()
        else:
            results['failed'] += 1
        time.sleep(SMS_DELAY_BETWEEN_RECIPIENTS)
    
    # Disconnect if we created the connection
    if should_disconnect:
        gsm_module.disconnect()
    
    # Print summary
    print("=" * 60)
    print("Alert Summary:")
    print(f"   Total recipients: {results['total']}")
    print(f"   Successfully sent: {results['success']}")
    print(f"   Failed: {results['failed']}")
    print("=" * 60)
    
    return results

def send_alert_to_all_recipients(message, gsm_module=None, cooldown_key="default", cooldown_seconds=None):
    """
    Send alert SMS to all active recipients.
    cooldown_key: different keys get separate cooldowns (e.g. threshold:DO vs marine:DO:critical).
    cooldown_seconds: if set, use this duration for this key instead of RECIPIENT_COOLDOWN_SECONDS.
    """
    if not _alert_send_lock.acquire(blocking=False):
        print("[INFO] Alert send already in progress; skipping this batch.")
        return {'total': 0, 'success': 0, 'failed': 0, 'recipients': []}
    try:
        return _send_alert_to_all_recipients_impl(message, gsm_module, cooldown_key, cooldown_seconds)
    finally:
        _alert_send_lock.release()


def _send_alert_to_all_recipients_impl(message, gsm_module=None, cooldown_key="default", cooldown_seconds=None):
    """Implementation of send_alert_to_all_recipients (called with lock held)."""
    phone_numbers = get_active_phone_numbers()
    
    if not phone_numbers:
        print("[WARN] No active recipients found in local database")
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'recipients': []
        }

    to_send = _recipients_past_cooldown(phone_numbers, cooldown_key, cooldown_seconds)
    skipped = len(phone_numbers) - len(to_send)
    if skipped:
        print(f"[INFO] Skipping {skipped} recipient(s) still in cooldown (key={cooldown_key!r})")
    if not to_send:
        print("[INFO] No recipients past cooldown; skipping send")
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'recipients': phone_numbers
        }
    
    print(f"Sending alert to {len(to_send)} recipient(s)...")
    
    # Initialize GSM module if not provided
    if gsm_module is None:
        gsm_module = create_gsm_module()
        if not gsm_module.connect():
            print("[ERROR] Failed to connect to GSM module")
            return {
                'total': len(to_send),
                'success': 0,
                'failed': len(to_send),
                'recipients': to_send
            }
        should_disconnect = True
    else:
        should_disconnect = False
    
    results = {
        'total': len(to_send),
        'success': 0,
        'failed': 0,
        'recipients': to_send
    }
    
    # Send SMS to each recipient (one at a time); record cooldown per number when send succeeds
    SMS_DELAY_BETWEEN_RECIPIENTS = 2.5  # seconds so modem can transmit before next
    for phone_number in to_send:
        if gsm_module.send_sms(phone_number, message):
            results['success'] += 1
            _last_alert_time_by_number[(phone_number, cooldown_key)] = time.time()
        else:
            results['failed'] += 1
        time.sleep(SMS_DELAY_BETWEEN_RECIPIENTS)
    
    if should_disconnect:
        gsm_module.disconnect()
    
    print("=" * 60)
    print("Alert Summary:")
    print(f"   Total recipients: {results['total']}")
    print(f"   Successfully sent: {results['success']}")
    print(f"   Failed: {results['failed']}")
    print("=" * 60)
    
    return results

def send_no_data_alert(phone_numbers):
    """
    Send device alert when no data is detected (display off/blank).
    Uses static phone numbers list.
    
    Args:
        phone_numbers: List of phone number strings (e.g. NO_DATA_ALERT_PHONES)
    
    Returns:
        dict: Results from send_alert_to_static_numbers
    """
    message = (
        "DEVICE ALERT\n\n"
        "No data detected from YK-100 device.\n"
        "The device display appears to be off or blank.\n\n"
        "Possible causes:\n"
        "- Device power off\n"
        "- Display malfunction\n"
        "- Connection issue\n\n"
        "Please check the device immediately."
    )
    return send_alert_to_static_numbers(phone_numbers, message)


def send_invalid_readings_alert(phone_numbers, invalid_params):
    """
    Send device alert when readings are invalid or incomplete.
    Uses static phone numbers list.
    
    Args:
        phone_numbers: List of phone number strings (e.g. NO_DATA_ALERT_PHONES)
        invalid_params: List of parameter names that are invalid/missing (e.g. ['TEMP', 'DO', 'EC'])
    
    Returns:
        dict: Results from send_alert_to_static_numbers
    """
    params_str = ", ".join(invalid_params) if invalid_params else "Unknown"
    message = (
        "DEVICE ALERT\n\n"
        "Invalid or incomplete readings from YK-100 device.\n"
        f"Missing or invalid: {params_str}\n\n"
        "Possible causes:\n"
        "- Device display off or blank\n"
        "- Sensor/connection issue\n"
        "- OCR could not read values\n\n"
        "Please check the device immediately."
    )
    return send_alert_to_static_numbers(phone_numbers, message)


def send_water_quality_alert(temperature, ph, dissolved_oxygen, salinity=None, tds=None, threshold_status=None, message_prefix=""):
    """
    Send water quality alert with sensor readings (threshold violation).
    Uses active recipients from database.
    Message uses ASCII-only characters for reliable SMS delivery (no degree/micro symbols).
    
    Args:
        temperature: Temperature value
        ph: pH value
        dissolved_oxygen: Dissolved oxygen value (mg/L)
        salinity: Salinity value (ppt), optional
        tds: TDS value (ppm), optional
        threshold_status: Optional dict with threshold status for each parameter
        message_prefix: Optional prefix (e.g. "PREDICTED ") for forecast alerts
    
    Returns:
        dict: Alert results
    """
    message = (message_prefix + "WATER QUALITY ALERT\n\n") if message_prefix else "WATER QUALITY ALERT\n\n"
    # Use "deg C" instead of degree symbol to avoid SMS encoding issues (e.g. turning into A@)
    message += f"Temperature: {temperature} deg C\n"
    message += f"pH: {ph}\n"
    message += f"Dissolved Oxygen: {dissolved_oxygen} mg/L\n"
    if salinity is not None:
        message += f"Salinity: {salinity} ppt\n"
    if tds is not None:
        message += f"TDS: {tds} ppm\n"
    
    if threshold_status:
        message += "\nThreshold Status:\n"
        for param, status in threshold_status.items():
            message += f"{param}: {status}\n"
    
    message += "\nPlease check the system immediately."
    
    # Separate cooldown per parameter(s) so e.g. Salinity/TDS alert does not block DO alert
    cooldown_key = "default"
    if threshold_status:
        cooldown_key = "threshold:" + ",".join(sorted(threshold_status.keys()))
    return send_alert_to_all_recipients(message, cooldown_key=cooldown_key)

# =====================================================
# TESTING
# =====================================================
if __name__ == "__main__":
    # Test: Send test alert
    print("Testing GSM alert system...")
    
    test_message = "TEST ALERT\n\nThis is a test message from the water quality monitoring system."
    results = send_alert_to_all_recipients(test_message)
    
    print(f"Test complete: {results['success']}/{results['total']} sent successfully")
