"""
ESP8266 HTTP Client for Raspberry Pi
Communicates with ESP8266 over WiFi to control GSM module and relay (aeration only).
Connection check (reachable or not) lives here; relay_control only holds relay state and the client.
"""

import time
import requests
from typing import Optional, Dict, List

from .esp8266_config import ESP8266_IP, ESP8266_PORT

# Default retries for check_esp_reachable (avoids false "disconnected" on transient failure)
CHECK_REACHABLE_RETRIES = 3
CHECK_REACHABLE_RETRY_DELAY_SEC = 1.5

# =====================================================
# CONFIGURATION
# =====================================================
REQUEST_TIMEOUT = 10  # seconds (for status, relay, etc.)
# SMS can take 15-45+ seconds (modem sends over cellular before ESP responds)
SMS_REQUEST_TIMEOUT = 45

# =====================================================
# ESP8266 CLIENT CLASS
# =====================================================
class ESP8266Client:
    """
    Client for communicating with ESP8266 GSM & Relay Controller.
    """
    
    def __init__(self, ip_address: str = ESP8266_IP, port: int = ESP8266_PORT):
        """
        Initialize ESP8266 client.
        
        Args:
            ip_address: ESP8266 IP address
            port: ESP8266 HTTP server port (default: 80)
        """
        self.ip_address = ip_address
        self.port = port
        self.base_url = f"http://{ip_address}:{port}"
        self.timeout = REQUEST_TIMEOUT
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     data: Optional[Dict] = None, timeout: Optional[int] = None,
                     silent: bool = False) -> Optional[requests.Response]:
        """
        Make HTTP request to ESP8266.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            params: URL parameters
            data: POST data
            timeout: Request timeout in seconds (default: self.timeout)
            silent: If True, do not print on error (e.g. for device-status checks)

        Returns:
            Response object or None on error
        """
        url = f"{self.base_url}{endpoint}"
        req_timeout = timeout if timeout is not None else self.timeout

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=req_timeout)
            elif method.upper() == "POST":
                response = requests.post(url, data=data, timeout=req_timeout)
            else:
                if not silent:
                    print(f"[ERROR] Unsupported HTTP method: {method}")
                return None

            return response
        except requests.exceptions.Timeout:
            if not silent:
                print(f"[ERROR] Request timeout: {url}")
            return None
        except requests.exceptions.ConnectionError:
            if not silent:
                print(f"[ERROR] Connection error: Cannot reach ESP8266 at {self.ip_address}")
            return None
        except Exception as e:
            if not silent:
                print(f"[ERROR] Request error: {e}")
            return None

    def check_connection(self, silent: bool = False) -> bool:
        """
        Check if ESP8266 is reachable (single attempt).

        Args:
            silent: If True, do not print on error (for device-status updates).

        Returns:
            bool: True if ESP8266 is reachable, False otherwise
        """
        response = self._make_request("GET", "/status", silent=silent)
        if response and response.status_code == 200:
            return True
        return False

    def get_status(self) -> Optional[Dict]:
        """
        Get ESP8266 device status.
        
        Returns:
            dict: Status information or None on error
            {
                "wifi": {"connected": bool, "ip": str},
                "gsm": {"initialized": bool},
                "relay": {"state": bool}
            }
        """
        response = self._make_request("GET", "/status")
        
        if response and response.status_code == 200:
            try:
                return response.json()
            except:
                return None
        return None
    
    def _send_sms_once(self, phone_number: str, message: str) -> bool:
        """Single attempt to send SMS via ESP8266. Returns True if HTTP 200."""
        data = {"number": phone_number, "message": message}
        url = f"{self.base_url}/send_sms"
        try:
            response = requests.post(url, data=data, timeout=SMS_REQUEST_TIMEOUT)
            if response and response.status_code == 200:
                print(f"SMS sent to {phone_number} via ESP8266")
                return True
            if response:
                print(f"[WARN] SMS to {phone_number} failed: HTTP {response.status_code}")
            return False
        except requests.exceptions.Timeout:
            print(f"[ERROR] SMS to {phone_number} timed out")
            return False
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] Cannot reach ESP8266 while sending to {phone_number}")
            return False
        except Exception as e:
            print(f"[ERROR] SMS to {phone_number} failed: {e}")
            return False

    def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Send SMS via ESP8266 GSM module with retry (no GSM relay reset).
        Attempt 1 -> Attempt 2 -> wait 10s -> Attempt 3. Returns True if any attempt succeeds.
        """
        if self._send_sms_once(phone_number, message):
            return True
        if self._send_sms_once(phone_number, message):
            return True
        print("[WARN] SMS failed twice; waiting 10s then retrying once...")
        time.sleep(10)
        return self._send_sms_once(phone_number, message)
    
    def set_relay(self, state: bool) -> bool:
        """
        Control relay via ESP8266.
        
        Args:
            state: True to turn ON, False to turn OFF
        
        Returns:
            bool: True if successful, False otherwise
        """
        data = {
            "state": "ON" if state else "OFF"
        }
        
        response = self._make_request("POST", "/relay", data=data)
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                if result.get("success", False):
                    relay_state = "ON" if state else "OFF"
                    print(f"Relay set to {relay_state} via ESP8266")
                    return True
                else:
                    print(f"[ERROR] Relay control failed: {result.get('error', 'Unknown error')}")
                    return False
            except:
                print("[ERROR] Failed to parse relay response")
                return False
        else:
            print(f"[ERROR] Relay request failed (status: {response.status_code if response else 'No response'})")
            return False
    
    def get_relay_status(self) -> Optional[bool]:
        """
        Get current relay status.
        
        Returns:
            bool: True if relay is ON, False if OFF, None on error
        """
        response = self._make_request("GET", "/relay/status")
        
        if response and response.status_code == 200:
            try:
                result = response.json()
                if result.get("success", False):
                    return result.get("relay", False)
            except:
                return None
        return None
    
    def activate_relay(self) -> bool:
        """Activate relay (turn ON)"""
        return self.set_relay(True)
    
    def deactivate_relay(self) -> bool:
        """Deactivate relay (turn OFF)"""
        return self.set_relay(False)


def check_esp_reachable(
    client: Optional[ESP8266Client],
    silent: bool = False,
    retries: int = CHECK_REACHABLE_RETRIES,
    retry_delay_sec: float = CHECK_REACHABLE_RETRY_DELAY_SEC,
) -> bool:
    """
    Check if ESP8266 is reachable (GET /status). Use this for device-status or any
    non-relay code that needs to know connectivity. Retries to avoid transient false negatives.

    Args:
        client: ESP8266Client instance (e.g. from relay_control.get_esp_client()); None => False.
        silent: If True, client does not print on error (e.g. for device-status updates).
        retries: Number of attempts.
        retry_delay_sec: Delay between attempts.

    Returns:
        True if ESP responded with 200, False otherwise.
    """
    if client is None:
        return False
    for attempt in range(retries):
        try:
            if client.check_connection(silent=silent):
                return True
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(retry_delay_sec)
    return False


# =====================================================
# GSM MODULE WRAPPER (Compatible with existing code)
# =====================================================
class GSMViaESP8266:
    """
    GSM module wrapper that uses ESP8266 instead of direct serial connection.
    Compatible with existing GSMModule interface.
    """
    
    def __init__(self, esp8266_client: Optional[ESP8266Client] = None):
        """
        Initialize GSM via ESP8266.
        
        Args:
            esp8266_client: ESP8266Client instance (will create if not provided)
        """
        if esp8266_client is None:
            self.client = ESP8266Client()
        else:
            self.client = esp8266_client
        self.initialized = False
    
    def connect(self) -> bool:
        """
        Check ESP8266 connection (compatible with GSMModule interface).
        
        Returns:
            bool: True if ESP8266 is reachable, False otherwise
        """
        if self.client.check_connection():
            status = self.client.get_status()
            if status and status.get("gsm", {}).get("initialized", False):
                self.initialized = True
                print("GSM module connected via ESP8266")
                return True
            else:
                print("[WARN] ESP8266 connected but GSM module not initialized")
                self.initialized = False
                return False
        else:
            print("[ERROR] Cannot connect to ESP8266")
            self.initialized = False
            return False
    
    def disconnect(self):
        """Disconnect (no-op for HTTP client)"""
        self.initialized = False
        print("GSM module disconnected")
    
    def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Send SMS via ESP8266.
        
        Args:
            phone_number: Recipient phone number
            message: SMS message text
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.initialized:
            print("[WARN] GSM module not initialized")
            return False
        
        return self.client.send_sms(phone_number, message)
    
    def send_at_command(self, command: str, timeout: int = 5) -> Optional[str]:
        """
        Send AT command (not supported via HTTP, returns None).
        This method exists for compatibility but doesn't work via HTTP.
        
        Args:
            command: AT command string
            timeout: Timeout in seconds (ignored)
        
        Returns:
            None (AT commands not supported via HTTP)
        """
        print("[WARN] AT commands not supported via HTTP interface")
        return None


# =====================================================
# TESTING
# =====================================================
if __name__ == "__main__":
    print("Testing ESP8266 client...")
    
    # Create client
    client = ESP8266Client()
    
    # Check connection
    print("\n1. Checking connection...")
    if client.check_connection():
        print("ESP8266 is reachable")
    else:
        print("[ERROR] ESP8266 is not reachable")
        print("   Make sure ESP8266 is connected to WiFi and IP is correct")
        exit(1)
    
    # Get status
    print("\n2. Getting device status...")
    status = client.get_status()
    if status:
        print(f"   WiFi IP: {status.get('wifi', {}).get('ip', 'Unknown')}")
        print(f"   GSM Initialized: {status.get('gsm', {}).get('initialized', False)}")
        print(f"   Relay State: {status.get('relay', {}).get('state', False)}")
    
    # Test relay control
    print("\n3. Testing relay control...")
    print("   Turning relay ON...")
    client.activate_relay()
    time.sleep(2)
    
    print("   Turning relay OFF...")
    client.deactivate_relay()
    time.sleep(1)
    
    # Test SMS (uncomment to test - requires valid phone number)
    # print("\n4. Testing SMS...")
    # client.send_sms("09123456789", "Test message from ESP8266")
    
    print("\nTest complete!")
