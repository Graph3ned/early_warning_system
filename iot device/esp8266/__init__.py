"""
ESP8266 WiFi client and configuration for GSM and relay control.

Configure IP and port in esp8266_config.py. Connection reachability is implemented in
esp8266_client (check_esp_reachable).
"""

from .esp8266_config import ESP8266_IP, ESP8266_PORT
from .esp8266_client import ESP8266Client, GSMViaESP8266, check_esp_reachable

__all__ = ["ESP8266_IP", "ESP8266_PORT", "ESP8266Client", "GSMViaESP8266", "check_esp_reachable"]
