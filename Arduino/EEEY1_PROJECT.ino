#include <SPI.h>
#include <WiFi101.h>
#include <WiFiUdp.h>

char WIFI_SSID[] = "LAPTOP-IQV3I9AI 4829";
char WIFI_PASS[] = "3047Bd}0"; // Make sure this is your correct password

// --- WiFi Connection Status ---
int status = WL_IDLE_STATUS;

// --- MUX Pin ---
const int MUXSel = 6;

// --- Square Wave Gen ---
const int squareWaveOutputPin = 11;
const unsigned int waveFrequency = 40000; // 40 kHz

// --- UDP Settings ---
WiFiUDP Udp;
unsigned int localUdpPort = 1000;       // Arduino listens for commands on this port
const unsigned int PYTHON_LISTEN_PORT = 1001; // Arduino sends data TO this port on Python PC
const int PACKET_BUFFER_SIZE = 32;

char rbtCmdPacketBuffer[PACKET_BUFFER_SIZE];
char freqSendBuffer[PACKET_BUFFER_SIZE];
char UARTSendBuffer[PACKET_BUFFER_SIZE];
char magneticSendBuffer[PACKET_BUFFER_SIZE];
char irSendBuffer[PACKET_BUFFER_SIZE];

// --- UART Settings ---
char uartDataPacketBuffer[5];
int uartDataCharCount = 0;
unsigned long lastUartCharTime = 0;
const unsigned long UART_INTER_CHAR_TIMEOUT = 250;

#define UART_SERIAL Serial1
#define UART_BAUD_RATE 600

// --- Controller Address (Python Script) ---
IPAddress controllerIP;
bool controllerAddressKnown = false;

// --- Motor Control Pins ---
const int motorPinL = 2;
const int motorPinLEn = 8;
const int motorPinR = 3;
const int motorPinREn = 9;

// --- Frequency Calculation ---
const int amSignalIn = 0;
long count = 0;
unsigned long previousMillis = 0;
const long interval = 300;
boolean lastInputState = false;

// --- Magnetic Sensor ---
const int magneticSensorPin = A0;
unsigned long lastMagReadTime = 0;
const unsigned long MAG_READ_INTERVAL = 200; // How often to read the sensor (ms)
const float Vref = 5.0;
const int analogMax = 1023;

// --- IR Pulse Detection (Polling Method) ---
const int IR_PULSE_PIN = A1;
volatile unsigned long ir_lastMicros = 0;
volatile unsigned long ir_period_us  = 0;
volatile bool          ir_freshFlag  = false;

// --- State Machine ---
enum OperatingMode {
  READING_UART,
  READING_FREQUENCY
};
OperatingMode currentMode = READING_UART;

void setup() {
  Serial.begin(9600);
  while (!Serial);
  Serial.println("Robot Control Setup");

  pinMode(motorPinL, OUTPUT);
  pinMode(motorPinR, OUTPUT);
  pinMode(motorPinLEn, OUTPUT);
  pinMode(motorPinREn, OUTPUT);
  
  pinMode(MUXSel, OUTPUT);
  
  // amSignalIn pin mode can be safely set once here.
  pinMode(amSignalIn, INPUT);

  pinMode(IR_PULSE_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(IR_PULSE_PIN), irPulseISR, RISING);
  
  stopMotors();
  Serial.println("Motor pins initialized.");

  // Perform initial setup for the starting mode (UART)
  currentMode = READING_UART;
  digitalWrite(MUXSel, HIGH);
  UART_SERIAL.begin(UART_BAUD_RATE, SERIAL_8N1);
  Serial.println("Starting in UART mode.");

  // --- WiFi and UDP Setup (unchanged) ---
  Serial.print("Checking WiFi module... ");
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("WiFi shield not present!");
    while (true);
  }
  Serial.println("Module detected.");

  Serial.print("Attempting to connect to SSID: ");
  Serial.println(WIFI_SSID);
  status = WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long connectStartMillis = millis();
  while (status != WL_CONNECTED && millis() - connectStartMillis < 30000) {
    Serial.print(".");
    delay(1000);
    status = WiFi.status();
  }

  if (status == WL_CONNECTED) {
    Serial.println("\nConnected to WiFi!");
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
    while (1);
  }

  tone(squareWaveOutputPin, waveFrequency);
}

// --- Main Non-Blocking Loop ---
void loop() {
  // Always check for new robot commands, regardless of the current mode
  handleUdpCommands();
  handleMagneticSensor();
  handleIrPulse();

  // State machine to switch between reading UART and calculating frequency
  if (currentMode == READING_UART) {
    handleUart();
  } else { // currentMode == READING_FREQUENCY
    handleAMFrequency();
  }
}

// --- Task Handling Functions ---

void handleUdpCommands() {
  int packetSize = Udp.parsePacket();
  if (packetSize > 0) {
    if (!controllerAddressKnown || Udp.remoteIP() != controllerIP) {
      controllerIP = Udp.remoteIP();
      controllerAddressKnown = true;
      Serial.print("Controller address registered: ");
      Serial.println(controllerIP);
    }

    int len = Udp.read(rbtCmdPacketBuffer, PACKET_BUFFER_SIZE - 1);
    if (len > 0) {
      rbtCmdPacketBuffer[len] = '\0';
      processCommand(rbtCmdPacketBuffer);
    }
  }
}

void irPulseISR() {
  unsigned long now = micros();
  unsigned long delta = now - ir_lastMicros;

  // Debounce/noise filter: ignore pulses that are too fast (e.g., > 5 kHz)
  // and ignore the very first pulse after startup.
  if (ir_lastMicros != 0 && delta > 200) {
    ir_period_us = delta;
    ir_freshFlag = true; // Signal the main loop that we have fresh data
  }
  ir_lastMicros = now;
}

void handleIrPulse() {
  if (!ir_freshFlag) { return; }

  unsigned long period_us_copy;

  // Disable interrupts briefly to safely copy the volatile variable.
  // This prevents the ISR from changing ir_period_us while we're reading it.
  noInterrupts();
  period_us_copy = ir_period_us;
  ir_freshFlag = false; // Reset the flag so we don't process the same data twice
  interrupts();

  // Slower calculations and network communication
  if (period_us_copy > 0) {
    float frequency = 1000000.0f / period_us_copy;

    Serial.print("IR Freq: ");
    Serial.println(frequency);

    // Send the raw frequency value over UDP
    if (controllerAddressKnown) {
      sprintf(irSendBuffer, "IR:%.2f", frequency);
      Udp.beginPacket(controllerIP, PYTHON_LISTEN_PORT);
      Udp.write((uint8_t*)irSendBuffer, strlen(irSendBuffer));
      Udp.endPacket();
    }
  }
}

void handleMagneticSensor() {
  // Check if it's time to read the sensor again
  if (millis() - lastMagReadTime >= MAG_READ_INTERVAL) {
    lastMagReadTime = millis(); // Update the timer

    int sensorValue = analogRead(magneticSensorPin);
    float voltage = (float)sensorValue * (Vref / (float)analogMax);
    char polarityStr[10];

    if (voltage < 2.2) {
      strcpy(polarityStr, "South");
    } else if (voltage > 0.8) {
      strcpy(polarityStr, "North");
    } else {
      strcpy(polarityStr, "Unknown");
    }

    Serial.print("Mag: ");
    Serial.println(polarityStr);

    // Only send if we know who to send to
    if (controllerAddressKnown) {
      sprintf(magneticSendBuffer, "MAG:%s", polarityStr);
      Udp.beginPacket(controllerIP, PYTHON_LISTEN_PORT);
      Udp.write((uint8_t*)magneticSendBuffer, strlen(magneticSendBuffer));
      Udp.endPacket();
    }
  }
}

void handleUart() {
  if (UART_SERIAL.available() > 0) {
    byte incomingUARTByte = UART_SERIAL.read();
    lastUartCharTime = millis();

    if (uartDataCharCount < 4) {
      uartDataPacketBuffer[uartDataCharCount++] = (char)incomingUARTByte;

      if (uartDataCharCount == 4) {
        uartDataPacketBuffer[4] = '\0';
        if (controllerAddressKnown) {
          sprintf(UARTSendBuffer, "UART_PKT:%s", uartDataPacketBuffer);
          Udp.beginPacket(controllerIP, PYTHON_LISTEN_PORT);
          Udp.write((uint8_t*)UARTSendBuffer, strlen(UARTSendBuffer));
          Udp.endPacket();
          switchToMode(READING_FREQUENCY);
        }
        uartDataCharCount = 0;
      }
    }
  }

  if (uartDataCharCount > 0 && (millis() - lastUartCharTime > UART_INTER_CHAR_TIMEOUT)) {
    uartDataPacketBuffer[uartDataCharCount] = '\0';
    if (controllerAddressKnown) {
      sprintf(UARTSendBuffer, "UART_FAIL:%s", uartDataPacketBuffer);
      Udp.beginPacket(controllerIP, PYTHON_LISTEN_PORT);
      Udp.write((uint8_t*)UARTSendBuffer, strlen(UARTSendBuffer));
      Udp.endPacket();
      switchToMode(READING_FREQUENCY);
    }
    uartDataCharCount = 0;
  }
}

void handleAMFrequency() {
  bool value = digitalRead(amSignalIn);
  if (value != lastInputState) {
    count++;
    lastInputState = value;
  }

  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= interval) {
    unsigned long interval = currentMillis - previousMillis;
    previousMillis = currentMillis;

    float hertz = 0.0;
    if (interval > 0) {
      // We count both rising and falling edges, so `count` is twice the
      // number of full cycles. We must divide the count by 2.
      hertz = ((float)count / 2.0f) / ((float)interval / 1000.0f);
    }

    if (controllerAddressKnown) {
      sprintf(freqSendBuffer, "FREQ:%.2f", hertz);
      Udp.beginPacket(controllerIP, PYTHON_LISTEN_PORT);
      Udp.write((uint8_t*)freqSendBuffer, strlen(freqSendBuffer));
      Udp.endPacket();
    }

    count = 0; // Reset counter for the next measurement window
    switchToMode(READING_UART);
  }
}

void switchToMode(OperatingMode newMode) {
  // Only perform actions if the mode is actually changing
  if (currentMode == newMode) return; 

  currentMode = newMode;
  
  if (currentMode == READING_UART) {
    // Configure hardware for UART reading
    digitalWrite(MUXSel, HIGH);
    UART_SERIAL.begin(UART_BAUD_RATE, SERIAL_8N1);
    delay(100);
    Serial.println("Switched to UART mode.");
  } else { // READING_FREQUENCY
    // Configure hardware for Frequency counting
    UART_SERIAL.end(); // Disable UART to avoid receiving junk data
    digitalWrite(MUXSel, LOW);

    // Reset the frequency timer and counter at the start of the mode.
    previousMillis = millis();
    count = 0;
    lastInputState = digitalRead(amSignalIn);

    delay(100);
    Serial.println("Switched to Frequency mode.");
  }
}


// --- Motor Control Functions (processCommand, moveForward, etc. are unchanged) ---
void processCommand(const char* command) {
  if (strcmp(command, "FF") == 0) {
    moveForward(true, false);
  } else if (strcmp(command, "BF") == 0) {
    moveBackward(true, false);
  } else if (strcmp(command, "LF") == 0) {
    turnLeft(true, false);
  } else if (strcmp(command, "RF") == 0) {
    turnRight(true, false);
  } else if (strcmp(command, "FS") == 0) {
    moveForward(false, true);
  } else if (strcmp(command, "BS") == 0) {
    moveBackward(false, true);
  } else if (strcmp(command, "LS") == 0) {
    turnLeft(false, true);
  } else if (strcmp(command, "RS") == 0) {
    turnRight(false, true);
  } else if (strcmp(command, "F") == 0) {
    moveForward(false, false);
  } else if (strcmp(command, "B") == 0) {
    moveBackward(false, false);
  } else if (strcmp(command, "L") == 0) {
    turnLeft(false, false);
  } else if (strcmp(command, "R") == 0) {
    turnRight(false, false);
  } else if (strcmp(command, "S") == 0) {
    stopMotors();
  } else {
    Serial.println("Unknown command received.");
    stopMotors();
  }
}

int get_speed(bool fast = false, bool slow = false) {
  if (fast) return 255;
  if (slow) return 80;
  return 220;
}

void moveForward(bool fast, bool slow) {
  int value = get_speed(fast, slow);
  digitalWrite(motorPinL, LOW);
  analogWrite(motorPinLEn, value);
  digitalWrite(motorPinR, HIGH);
  analogWrite(motorPinREn, value);
}

void moveBackward(bool fast, bool slow) {
  int value = get_speed(fast, slow);
  digitalWrite(motorPinL, HIGH);
  analogWrite(motorPinLEn, value);
  digitalWrite(motorPinR, LOW);
  analogWrite(motorPinREn, value);
}

void turnLeft(bool fast, bool slow) {
  int value = get_speed(fast, slow);
  digitalWrite(motorPinL, HIGH);
  analogWrite(motorPinLEn, value);
  digitalWrite(motorPinR, HIGH);
  analogWrite(motorPinREn, value);
}

void turnRight(bool fast, bool slow) {
  int value = get_speed(fast, slow);
  digitalWrite(motorPinL, LOW);
  analogWrite(motorPinLEn, value);
  digitalWrite(motorPinR, LOW);
  analogWrite(motorPinREn, value);
}

void stopMotors() {
  analogWrite(motorPinLEn, 0);
  analogWrite(motorPinREn, 0);
}
