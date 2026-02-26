// =============================================
// ESP32 EKG WebSocket Client
// Arduino UNO'dan seri veri alir, FastAPI sunucusuna iletir
// =============================================
// Gerekli kutuphane: arduinoWebSockets by Links2004
// Arduino IDE > Library Manager > "WebSockets" by Markus Sattler

#include <WiFi.h>
#include <WebSocketsClient.h>

// ---- WiFi Ayarlari ----
//WiFi login bilgileri (ESP32 + bilgisayar local agda olmali)
const char* WIFI_SSID     = "WIFI_ADI";
const char* WIFI_PASSWORD = "WIFI_SIFRE";

// ---- FastAPI Sunucu Ayarlari ----
// Uzak sunucu adresi (domain veya IP)
const char* SERVER_HOST = "ekg.seninsunucun.com";
const uint16_t SERVER_PORT = 443;      // HTTPS=443, HTTP=8000
const char* WS_PATH = "/ws/device";
const bool USE_SSL = true;             // HTTPS sunucu icin true

// ---- Pin Ayarlari ----
#define RXD2 16  // ESP32 RX2 <- Arduino TX
#define TXD2 17  // ESP32 TX2 (kullanilmiyor)

WebSocketsClient webSocket;

// Veri tamponu
String dataBuffer = "";
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 20; // 20ms batch

bool wsConnected = false;

// Dahili LED (baglanti gostergesi)
#define LED_PIN 2

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      wsConnected = false;
      digitalWrite(LED_PIN, LOW);
      Serial.println("[WS] Sunucu baglantisi kesildi");
      break;

    case WStype_CONNECTED:
      wsConnected = true;
      digitalWrite(LED_PIN, HIGH);
      Serial.println("[WS] Sunucuya baglandi!");
      break;

    case WStype_TEXT:
      // Sunucudan gelen komutlar (ileride kullanilabilir)
      break;

    case WStype_PING:
    case WStype_PONG:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("\n=== EKG WebSocket Client ===");

  // WiFi baglantisi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi'ye baglaniyor");

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("WiFi baglandi! IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi baglantisi basarisiz! Yeniden deneniyor...");
    ESP.restart();
  }

  // WebSocket client baslat
  if (USE_SSL) {
    webSocket.beginSSL(SERVER_HOST, SERVER_PORT, WS_PATH);
    Serial.printf("Sunucu: wss://%s:%d%s\n", SERVER_HOST, SERVER_PORT, WS_PATH);
  } else {
    webSocket.begin(SERVER_HOST, SERVER_PORT, WS_PATH);
    Serial.printf("Sunucu: ws://%s:%d%s\n", SERVER_HOST, SERVER_PORT, WS_PATH);
  }
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(3000);
}

void loop() {
  webSocket.loop();

  // WiFi koptu mu kontrol
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi baglantisi koptu, yeniden baslatiliyor...");
    delay(1000);
    ESP.restart();
  }

  // Arduino'dan veri oku (seri)
  while (Serial2.available()) {
    String line = Serial2.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      dataBuffer += line + "\n";
    }
  }

  // Toplu gonder
  unsigned long now = millis();
  if (now - lastSend >= SEND_INTERVAL && dataBuffer.length() > 0 && wsConnected) {
    webSocket.sendTXT(dataBuffer);
    dataBuffer = "";
    lastSend = now;
  }

  // Buffer tasmasin (baglanti yokken)
  if (dataBuffer.length() > 1024) {
    dataBuffer = "";
  }
}
