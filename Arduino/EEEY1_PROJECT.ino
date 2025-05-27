#include <SPI.h>
#include <WiFi101.h>
#include <WiFiUdp.h>

char WIFI_SSID[] = "LAPTOP-IQV3I9AI 4829";
char WIFI_PASS[] = "3047Bd}0"; // Make sure this is your correct password

// --- WiFi Connection Status ---
int status = WL_IDLE_STATUS;

// --- UDP Settings ---
WiFiUDP Udp;
unsigned int localUdpPort = 1000;       // Arduino listens for commands on this port
const unsigned int PYTHON_LISTEN_PORT = 1001; // Arduino sends frequency TO this port on Python PC
const int PACKET_BUFFER_SIZE = 32; // Increased slightly for "FREQ:xx.xx"
char packetBuffer[PACKET_BUFFER_SIZE];
char freqSendBuffer[PACKET_BUFFER_SIZE]; // Buffer to format frequency string

// --- Controller Address (Python Script) ---
IPAddress controllerIP; // IP of the Python script
bool controllerAddressKnown = false;

// --- Motor Control Pins ---
const int motorPinL = 2;
const int motorPinLEn = 8;
const int motorPinR = 3;
const int motorPinREn = 9;

// --- Frequency Calculation ---
const int amSignalIn = 6;
long count = 0;
unsigned long previousMillis = 0;
const long interval = 500; // Calculate frequency every 500 ms
boolean lastInputState = false; // Initialize to false

void setup() {
  Serial.begin(9600);
  while (!Serial)
    ;
  Serial.println("Robot Control Setup");

  pinMode(motorPinL, OUTPUT);
  pinMode(motorPinR, OUTPUT);
  pinMode(motorPinLEn, OUTPUT);
  pinMode(motorPinREn, OUTPUT);
  pinMode(amSignalIn, INPUT);

  stopMotors();
  Serial.println("Motor pins initialized.");

  Serial.print("Checking WiFi module... ");
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("WiFi shield not present!");
    while (true);
  }
  Serial.println("Module detected.");

  Serial.print("Attempting to connect to SSID: ");
  Serial.println(WIFI_SSID);
  status = WiFi.begin(WIFI_SSID, WIFI_PASS); // Initial attempt
  unsigned long connectStartMillis = millis();
  while (status != WL_CONNECTED && millis() - connectStartMillis < 30000) { // 30 sec timeout
    Serial.print(".");
    delay(1000); // Wait before retrying status check
    status = WiFi.status();
  }

  if (status == WL_CONNECTED) {
    Serial.println("\nConnected to WiFi!");
    printWifiStatus();
    Serial.println("Waiting a moment for network stack...");
    delay(500);
    Serial.print("Starting UDP listener for commands on port ");
    Serial.println(localUdpPort);
    if (Udp.begin(localUdpPort)) {
      Serial.println("UDP command listener started successfully.");
    } else {
      Serial.println("Failed to start UDP command listener!");
      while (1) { delay(100); }
    }
  } else {
    Serial.print("\nFailed to connect. Final Status: ");
    Serial.println(status);
    while(1); // Halt
  }
}

void loop() {
  // --- Command Receiving ---
  int packetSize = Udp.parsePacket();
  if (packetSize > 0) {
    if (!controllerAddressKnown || Udp.remoteIP() != controllerIP) {
        controllerIP = Udp.remoteIP();
        controllerAddressKnown = true;
        Serial.print("Controller address registered: ");
        Serial.println(controllerIP);
    }
    
    // Serial.print("Received packet of size "); // Verbose Arduino debug
    // Serial.print(packetSize);
    // Serial.print(" from ");
    // Serial.print(Udp.remoteIP());
    // Serial.print(", port ");
    // Serial.println(Udp.remotePort());

    int len = Udp.read(packetBuffer, PACKET_BUFFER_SIZE -1 ); // Leave space for null terminator
    if (len > 0) {
      packetBuffer[len] = '\0'; // Null-terminate
    }

    // Serial.print("UDP Packet Contents: "); Serial.println(packetBuffer); // Verbose Arduino debug

    if (len > 0) {
      processCommand(packetBuffer[0]);
    }
  }
  
  // --- Frequency Calculation and Sending ---
  boolean value = digitalRead(amSignalIn);
  if (value != lastInputState) {
    count++;
    lastInputState = value;
  }

  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis; // More accurate to set to currentMillis
    float frequency = (float)count / 2.0f / ((float)interval / 1000.0f); // Corrected calculation

    if (controllerAddressKnown) {
      // Serial.print("Raw Freq: "); // debugging
      // Serial.print(frequency);
      // Serial.println(" Hz");

      // Format frequency data: "FREQ:value"
      sprintf(freqSendBuffer, "FREQ:%.2f", frequency);
      
      Udp.beginPacket(controllerIP, PYTHON_LISTEN_PORT);
      Udp.write((uint8_t*)freqSendBuffer, strlen(freqSendBuffer));
      Udp.endPacket();
      // Serial.print("Sent to Python: "); Serial.println(freqSendBuffer); // Arduino debug
    }
    count = 0;
  }
}

// --- Motor Control Functions (processCommand, moveForward, etc.) ---
void processCommand(char command) {
  switch (command) {
    case 'F':
      moveForward();
      break;
    case 'B':
      moveBackward();
      break;
    case 'L':
      turnLeft();
      break;
    case 'R':
      turnRight();
      break;
    case 'S': 
    default:
      stopMotors();
      break;
  }
}
void moveForward() {
  digitalWrite(motorPinL, LOW);
  analogWrite(motorPinLEn, 250);
  digitalWrite(motorPinR, HIGH);
  analogWrite(motorPinREn, 250);
}

void moveBackward() {
  digitalWrite(motorPinL, HIGH);
  analogWrite(motorPinLEn, 250);
  digitalWrite(motorPinR, LOW);
  analogWrite(motorPinREn, 250);
  }

void turnLeft() {
  digitalWrite(motorPinL, HIGH);
  analogWrite(motorPinLEn, 250);
  digitalWrite(motorPinR, HIGH);
  analogWrite(motorPinREn, 250);
}

void turnRight() {
  digitalWrite(motorPinL, LOW);
  analogWrite(motorPinLEn, 250);
  digitalWrite(motorPinR, LOW);
  analogWrite(motorPinREn, 250);
}

void stopMotors() {
  analogWrite(motorPinLEn, 0);
  analogWrite(motorPinREn, 0);
}

// --- Utility Functions ---
void printWifiStatus() {
  Serial.print("SSID: "); Serial.println(WiFi.SSID());
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: "); Serial.println(ip);
  long rssi = WiFi.RSSI();
  Serial.print("Signal strength (RSSI):"); Serial.print(rssi); Serial.println(" dBm");
}