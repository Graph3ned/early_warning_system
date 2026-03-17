"""
Aeration relay control via ESP8266 HTTP API.

Maintains relay state and the shared ESP8266 client. Connection reachability is checked in the
esp8266 module (check_esp_reachable).
"""

from typing import Optional

from esp8266 import ESP8266_IP, ESP8266_PORT, ESP8266Client

relay_state = False
_esp8266_client = None
# True = last contact with ESP succeeded; False = init failed or relay call failed. Used for device_status.
esp_connected = False


def get_esp_client() -> Optional[ESP8266Client]:
    """Return the shared ESP8266 client (used by device-status check, etc.)."""
    return _esp8266_client


def init_relay():
    global relay_state, _esp8266_client, esp_connected
    try:
        _esp8266_client = ESP8266Client(ip_address=ESP8266_IP, port=ESP8266_PORT)
        if _esp8266_client.check_connection():
            current = _esp8266_client.get_relay_status()
            if current is not None:
                relay_state = current
            # Always set relay to OFF on startup (known safe state)
            if _esp8266_client.deactivate_relay():
                relay_state = False
                esp_connected = True
                print(f"Relay set to OFF at startup (ESP8266 at {ESP8266_IP})")
            else:
                esp_connected = True  # we did reach ESP
                print(f"Relay initialized via ESP8266 at {ESP8266_IP} (could not force OFF)")
            return True
        print(f"[ERROR] Cannot connect to ESP8266 at {ESP8266_IP}")
        esp_connected = False
        return False
    except ImportError:
        print("[ERROR] ESP8266 client not available. Install requests: pip install requests")
        esp_connected = False
        return False
    except Exception as e:
        print(f"[ERROR] Error initializing ESP8266 relay: {e}")
        esp_connected = False
        return False


def activate_relay():
    global relay_state, esp_connected
    if _esp8266_client is None:
        print("[ERROR] ESP8266 client not initialized")
        esp_connected = False
        return False
    try:
        if _esp8266_client.activate_relay():
            relay_state = True
            esp_connected = True
            return True
        esp_connected = False
        return False
    except Exception as e:
        print(f"[ERROR] Error activating relay via ESP8266: {e}")
        esp_connected = False
        return False


def deactivate_relay():
    global relay_state, esp_connected
    if _esp8266_client is None:
        print("[ERROR] ESP8266 client not initialized")
        esp_connected = False
        return False
    try:
        if _esp8266_client.deactivate_relay():
            relay_state = False
            esp_connected = True
            return True
        esp_connected = False
        return False
    except Exception as e:
        print(f"[ERROR] Error deactivating relay via ESP8266: {e}")
        esp_connected = False
        return False


def set_esp_connected(value: bool) -> None:
    """Set esp_connected (for relay/init success or when device-status check runs)."""
    global esp_connected
    esp_connected = value


def cleanup_relay():
    pass
