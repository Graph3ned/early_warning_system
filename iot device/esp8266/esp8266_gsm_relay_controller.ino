/*
 * ESP8266 GSM & Relay Controller
 * 
 * This firmware runs on ESP8266 to control:
 * - GSM module (SIM800L) for sending SMS
 * - Relay module for aerator control
 * 
 * Communication: WiFi HTTP REST API
 * 
 * Hardware Connections:
 * - GSM Module: RX->D5, TX->D6 (SoftwareSerial)
 * - Relay 1 (Aerator): D1 (GPIO 5)
 * - LED Status: D4 (GPIO 2) - Built-in LED
 * 
 * API Endpoints:
 * - GET /status - Get device status
 * - POST /send_sms - Send SMS (body: number=xxx&message=xxx)
 * - POST /relay - Control relay / aerator (body: state=ON or state=OFF)
 * - GET /relay/status - Get relay status
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <SoftwareSerial.h>

// =====================================================
// CONFIGURATION - MODIFY THESE VALUES
// =====================================================
const char* ssid = "Globewifis";           // Your WiFi network name
const char* password = "bfir0239";    // Your WiFi password

// Network settings (optional - for static IP)
// Uncomment and modify if you want static IP
/*
IPAddress local_IP(192, 168, 1, 100);
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 255, 0);
*/

// Hardware pins
#define GSM_RX_PIN D5      // ESP8266 RX pin (connects to GSM TX)
#define GSM_TX_PIN D6      // ESP8266 TX pin (connects to GSM RX)
#define RELAY_PIN D1       // GPIO 5 - Relay (aerator)
#define STATUS_LED D4      // GPIO 2 - Built-in LED

// GSM settings
#define GSM_BAUDRATE 9600
#define SMS_TIMEOUT 30000  // 30 seconds

// =====================================================
// GLOBAL OBJECTS
// =====================================================
ESP8266WebServer server(80);
SoftwareSerial gsmSerial(GSM_RX_PIN, GSM_TX_PIN);  // RX, TX

// State variables
bool relayState = false;
bool gsmInitialized = false;
unsigned long lastGSMCheck = 0;
const unsigned long GSM_CHECK_INTERVAL = 30000;  // Check GSM every 30 seconds

// =====================================================
// GSM FUNCTIONS
// =====================================================
void initGSM() {
  Serial.println("Initializing GSM module...");
  gsmSerial.begin(GSM_BAUDRATE);
  delay(2000);  // Wait for GSM module to initialize
  
  // Test connection
  if (sendATCommand("AT", 2000)) {
    gsmInitialized = true;
    Serial.println("GSM module initialized.");
    
    // Configure GSM module
    sendATCommand("AT+CMGF=1", 1000);  // Set SMS text mode
    sendATCommand("AT+CNMI=2,2,0,0,0", 1000);  // Configure SMS notifications
    
    digitalWrite(STATUS_LED, LOW);  // LED ON = status good
  } else {
    gsmInitialized = false;
    Serial.println("GSM module not responding.");
    digitalWrite(STATUS_LED, HIGH);  // LED OFF = error
  }
}

String sendATCommand(String command, unsigned long timeout) {
  gsmSerial.flush();
  gsmSerial.println(command);
  
  unsigned long startTime = millis();
  String response = "";
  
  while (millis() - startTime < timeout) {
    if (gsmSerial.available()) {
      char c = gsmSerial.read();
      response += c;
      
      // Check for complete response
      if (response.indexOf("OK") >= 0 || response.indexOf("ERROR") >= 0) {
        break;
      }
    }
    delay(10);
  }
  
  response.trim();
  return response;
}

bool sendSMS(String phoneNumber, String message) {
  if (!gsmInitialized) {
    Serial.println("GSM not initialized.");
    return false;
  }
  
  Serial.print("Sending SMS to ");
  Serial.print(phoneNumber);
  Serial.print(": ");
  Serial.println(message);
  
  // Set SMS text mode
  if (sendATCommand("AT+CMGF=1", 2000).indexOf("OK") < 0) {
    Serial.println("Failed to set SMS text mode.");
    return false;
  }
  
  // Set recipient number
  String cmd = "AT+CMGS=\"" + phoneNumber + "\"";
  String response = sendATCommand(cmd, 2000);
  
  if (response.indexOf(">") < 0) {
    Serial.println("Failed to set recipient.");
    return false;
  }
  
  // Send message (end with Ctrl+Z = 0x1A)
  gsmSerial.print(message);
  gsmSerial.write(0x1A);  // Ctrl+Z
  
  // Wait for response
  unsigned long startTime = millis();
  response = "";
  
  while (millis() - startTime < SMS_TIMEOUT) {
    if (gsmSerial.available()) {
      char c = gsmSerial.read();
      response += c;
      
      if (response.indexOf("OK") >= 0) {
        Serial.println("SMS sent successfully.");
        return true;
      } else if (response.indexOf("ERROR") >= 0) {
        Serial.println("SMS send error.");
        return false;
      }
    }
    delay(100);
  }
  
  Serial.println("SMS timeout.");
  return false;
}

void checkGSMHealth() {
  if (millis() - lastGSMCheck > GSM_CHECK_INTERVAL) {
    lastGSMCheck = millis();
    
    if (!gsmInitialized || sendATCommand("AT", 2000).indexOf("OK") < 0) {
      Serial.println("GSM health check failed; reinitializing...");
      gsmInitialized = false;
      initGSM();
    }
  }
}

// =====================================================
// RELAY FUNCTIONS
// =====================================================
void initRelay() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);  // Start with aerator relay OFF
  relayState = false;
  Serial.println("Relay initialized (D1=aerator).");
}

void setRelay(bool state) {
  digitalWrite(RELAY_PIN, state ? HIGH : LOW);
  relayState = state;
  Serial.print("Relay: ");
  Serial.println(state ? "ON" : "OFF");
}

// =====================================================
// HTTP SERVER HANDLERS
// =====================================================
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><title>ESP8266 GSM & Relay Controller</title>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
  html += "<style>body{font-family:Arial;margin:20px;background:#f5f5f5;}";
  html += ".card{background:white;padding:20px;margin:10px 0;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}";
  html += "h1{color:#333;} .status{color:#28a745;} .error{color:#dc3545;}</style></head><body>";
  html += "<h1>ESP8266 GSM & Relay Controller</h1>";
  
  html += "<div class='card'><h2>Device Status</h2>";
  html += "<p><strong>WiFi:</strong> <span class='status'>Connected</span></p>";
  html += "<p><strong>IP Address:</strong> " + WiFi.localIP().toString() + "</p>";
  html += "<p><strong>GSM Status:</strong> " + String(gsmInitialized ? "<span class='status'>Initialized</span>" : "<span class='error'>Not Initialized</span>") + "</p>";
  html += "<p><strong>Relay Status:</strong> " + String(relayState ? "ON" : "OFF") + "</p>";
  html += "</div>";
  
  html += "<div class='card'><h2>API Endpoints</h2>";
  html += "<ul>";
  html += "<li><code>GET /status</code> - Get device status (JSON)</li>";
  html += "<li><code>POST /send_sms</code> - Send SMS (number=xxx&message=xxx)</li>";
  html += "<li><code>POST /relay</code> - Control relay (state=ON or state=OFF)</li>";
  html += "<li><code>GET /relay/status</code> - Get relay status (JSON)</li>";
  html += "</ul></div>";
  
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleStatus() {
  String json = "{";
  json += "\"wifi\":{\"connected\":true,\"ip\":\"" + WiFi.localIP().toString() + "\"},";
  json += "\"gsm\":{\"initialized\":" + String(gsmInitialized ? "true" : "false") + "},";
  json += "\"relay\":{\"state\":" + String(relayState ? "true" : "false") + "}";
  json += "}";
  
  server.send(200, "application/json", json);
}

void handleSendSMS() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed");
    return;
  }
  
  String phoneNumber = server.arg("number");
  String message = server.arg("message");
  
  if (phoneNumber.length() == 0 || message.length() == 0) {
    server.send(400, "application/json", "{\"success\":false,\"error\":\"Missing number or message parameter\"}");
    return;
  }
  
  bool success = sendSMS(phoneNumber, message);
  
  if (success) {
    server.send(200, "application/json", "{\"success\":true,\"message\":\"SMS sent successfully\"}");
  } else {
    server.send(500, "application/json", "{\"success\":false,\"error\":\"Failed to send SMS\"}");
  }
}

void handleRelay() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed");
    return;
  }
  
  String state = server.arg("state");
  state.toUpperCase();
  
  if (state == "ON" || state == "1" || state == "TRUE") {
    setRelay(true);
    server.send(200, "application/json", "{\"success\":true,\"relay\":\"ON\"}");
  } else if (state == "OFF" || state == "0" || state == "FALSE") {
    setRelay(false);
    server.send(200, "application/json", "{\"success\":true,\"relay\":\"OFF\"}");
  } else {
    server.send(400, "application/json", "{\"success\":false,\"error\":\"Invalid state. Use ON or OFF\"}");
  }
}

void handleRelayStatus() {
  String json = "{\"success\":true,\"relay\":" + String(relayState ? "true" : "false") + "}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  server.send(404, "text/plain", "Not Found");
}

// =====================================================
// SETUP
// =====================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("========================================");
  Serial.println("ESP8266 GSM & Relay Controller");
  Serial.println("========================================\n");
  
  // Initialize hardware
  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, HIGH);  // LED OFF initially
  
  initRelay();
  initGSM();
  
  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  // Optional: Set static IP (uncomment if needed)
  // WiFi.config(local_IP, gateway, subnet);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected.");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("MAC Address: ");
    Serial.println(WiFi.macAddress());
  } else {
    Serial.println("\nWiFi connection failed.");
    Serial.println("Device will continue but may not be accessible.");
  }
  
  // Setup HTTP server routes
  server.on("/", handleRoot);
  server.on("/status", handleStatus);
  server.on("/send_sms", handleSendSMS);
  server.on("/relay", handleRelay);
  server.on("/relay/status", handleRelayStatus);
  server.onNotFound(handleNotFound);
  
  server.begin();
  Serial.println("HTTP server started.");
  Serial.println("========================================\n");
}

// =====================================================
// LOOP
// =====================================================
void loop() {
  server.handleClient();
  checkGSMHealth();
  delay(10);
}