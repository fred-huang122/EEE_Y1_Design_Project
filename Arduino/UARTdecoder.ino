char nameBuffer[4];
int nameCharCount = 0;
bool expectingNameChars = false;
 
#define UART_SERIAL Serial1
#define UART_BAUD_RATE 600
 
void setup()
{
  Serial.begin(9600);
  while (!Serial);
  UART_SERIAL.begin(UART_BAUD_RATE, SERIAL_8N1);
}
 
void loop()
{
  if (UART_SERIAL.available() > 0) {
    byte incomingByte = UART_SERIAL.read();
    Serial.print(incomingByte);
    Serial.print("Received Byte DEC: ");
    Serial.print(incomingByte, DEC);
    Serial.print(", HEX: 0x");
    if (incomingByte < 0x10) { // Add leading zero for single-digit hex values
      Serial.print("0");
    }
    Serial.print(incomingByte, HEX);
    Serial.print(", As Char: '");
    Serial.write(incomingByte); // Serial.write() sends the byte as is
    Serial.println("'");
  }
}
