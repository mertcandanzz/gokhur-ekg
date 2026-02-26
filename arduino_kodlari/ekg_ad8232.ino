// =============================================
// AD8232 EKG - Arduino UNO
// Serial TX ile ESP32'ye veri gonderir
// =============================================

#define LO_PLUS  10   // Leads Off Detection +
#define LO_MINUS 11   // Leads Off Detection -
#define EKG_PIN  A0   // Analog EKG sinyali

void setup() {
  Serial.begin(115200);       // ESP32 ile ayni baud rate
  pinMode(LO_PLUS, INPUT);
  pinMode(LO_MINUS, INPUT);
}

void loop() {
  if (digitalRead(LO_PLUS) == 1 || digitalRead(LO_MINUS) == 1) {
    Serial.println("!");      // Lead-off durumu
  } else {
    Serial.println(analogRead(EKG_PIN));
  }
  delay(2);  // ~500 Hz sampling
}
