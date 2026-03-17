"""
ESP8266 connection settings.

Single place to configure IP and port. When the ESP8266 obtains a new IP (e.g. after router or
WiFi change), update ESP8266_IP here. All consumers (main app, GSM alerts, tests) use this module.
"""

# Update when the ESP8266 IP address changes.
ESP8266_IP = "192.168.0.100"
ESP8266_PORT = 80
