
#include <SPI.h>
#include <WiFi101.h> // Use WiFiNINA for boards like Nano 33 IoT, MKR WiFi 1010
#include <WiFiUdp.h>

char WIFI_SSID[] = "LAPTOP-IQV3I9AI 4829";
char WIFI_PASS[] = "3047Bd}0";

// --- WiFi Connection Status ---
int status = WL_IDLE_STATUS;

// --- UDP Settings ---
WiFiUDP Udp;
unsigned int localUdpPort = 1000; // Port to listen on for commands
const int PACKET_BUFFER_SIZE = 24;
char packetBuffer[PACKET_BUFFER_SIZE]; // Buffer to hold incoming packet data

// --- Motor Control Pins ---
const int motorPinL = 2; // Pin for Left motor/side control
const int motorPinLEn = 8;
const int motorPinR = 3; // Pin for Right motor/side control
const int motorPinREn = 9;

void setup() {
  // Initialize Serial for debugging
  Serial.begin(9600);
  while (!Serial); // Wait for serial port to connect (needed for native USB)
  Serial.println("Robot Control Setup");

  // Initialize Motor Pins
  pinMode(motorPinL, OUTPUT);
  pinMode(motorPinR, OUTPUT);
  pinMode(motorPinLEn, OUTPUT);
  pinMode(motorPinREn, OUTPUT);

  stopMotors(); // Start with motors stopped
  Serial.println("Motor pins initialized.");

  // Check for the WiFi shield
  Serial.print("Checking WiFi module... ");
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("WiFi shield not present!");
    while (true); // Don't continue
  }
  Serial.println("Module detected.");

  // Attempt to connect to WiFi network
  Serial.print("Attempting to connect to SSID: ");
  Serial.println(WIFI_SSID);
  while (status != WL_CONNECTED) {
    Serial.print(".");
    // Connect to WPA/WPA2 network
    status = WiFi.begin(WIFI_SSID, WIFI_PASS);
    // Wait 5 seconds for connection:
    delay(5000);
  }

  if (status == WL_CONNECTED) {
    Serial.println("\nConnected to WiFi!");
    printWifiStatus();

    Serial.println("Waiting a moment for network stack...");
    delay(500);

    Serial.print("Starting UDP listener on port ");
    Serial.println(localUdpPort);
    if (Udp.begin(localUdpPort)) {
        Serial.println("UDP listener started successfully.");
    } else {
        Serial.println("Failed to start UDP listener!");
        // You might want to loop here or try again if UDP is essential
        while(1) { delay(100); }
    }
  } else {
    Serial.print("\nFailed to connect. Final Status: ");
    Serial.println(status); // Print the final failed status
  }
}

void loop() {
  // Check for incoming UDP packets
  int packetSize = Udp.parsePacket();
  if (packetSize > 0) {
    Serial.print("Received packet of size ");
    Serial.print(packetSize);
    Serial.print(" from ");
    IPAddress remoteIp = Udp.remoteIP();
    Serial.print(remoteIp);
    Serial.print(", port ");
    Serial.println(Udp.remotePort());

    // Read the packet into the buffer
    int len = Udp.read(packetBuffer, PACKET_BUFFER_SIZE);
    if (len > 0) {
      packetBuffer[len] = 0; // Null-terminate the received data
    }

    Serial.print("UDP Packet Contents: ");
    Serial.println(packetBuffer);

    // Process the command (use the first character)
    if (len > 0) {
       processCommand(packetBuffer[0]);
    }

    // Optional: Send a reply back to the sender
    // Udp.beginPacket(Udp.remoteIP(), Udp.remotePort());
    // Udp.write("ACK");
    // Udp.endPacket();
  }
  // Small delay to prevent loop from running too fast if needed
  delay(10);
}

// --- Motor Control Functions ---

void processCommand(char command) {
  Serial.print("Processing command: ");
  Serial.println(command);

  switch (command) {
    case 'F': // Forward
    case 'f':
      moveForward();
      break;
    case 'B': // Backward (If your H-bridge supports it with these pins)
    case 'b':
      moveBackward();
      break;
    case 'L': // Turn Left (Pivot Left - Right motor forward)
    case 'l':
      turnLeft();
      break;
    case 'R': // Turn Right (Pivot Right - Left motor forward)
    case 'r':
      turnRight();
      break;
    case 'S': // Stop
    case 's':
    default: // Stop on any other character
      stopMotors();
      break;
  }
}

void moveForward() {
  Serial.println("Moving Forward");
  digitalWrite(motorPinL, LOW);
  analogWrite(motorPinLEn, 250);

  digitalWrite(motorPinR, HIGH);  
  analogWrite(motorPinREn, 250);
}

void moveBackward() {
  Serial.println("Moving Backward");
  digitalWrite(motorPinL, HIGH);
  analogWrite(motorPinLEn, 250);

  digitalWrite(motorPinR, LOW);  
  analogWrite(motorPinREn, 250);
}

void turnLeft() {
  Serial.println("Turning Left");
  digitalWrite(motorPinL, HIGH);
  analogWrite(motorPinLEn, 250);

  digitalWrite(motorPinR, HIGH);  
  analogWrite(motorPinREn, 250);
  
}

void turnRight() {
  Serial.println("Turning Right");
  digitalWrite(motorPinL, LOW);
  analogWrite(motorPinLEn, 250);

  digitalWrite(motorPinR, LOW);  
  analogWrite(motorPinREn, 250);
}

void stopMotors() {
  Serial.println("Stopping Motors");
  analogWrite(motorPinLEn, 0);

  analogWrite(motorPinREn, 0);
}

// --- Utility Functions ---

void printWifiStatus() {
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print your board's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);

  // print the received signal strength:
  long rssi = WiFi.RSSI();
  Serial.print("Signal strength (RSSI):");
  Serial.print(rssi);
  Serial.println(" dBm");
}
