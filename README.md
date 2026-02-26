# Gokhur EKG

AD8232 EKG sensoru ile gercek zamanli kalp ritmi izleme sistemi. Arduino UNO sinyali okur, ESP32 WiFi uzerinden FastAPI backend'e iletir, modern dark-mode web arayuzu canli EKG grafigi cizer.

```
AD8232 ─(analog)─► Arduino UNO ─(serial)─► ESP32 ─(WiFi/WebSocket)─► FastAPI ─(WebSocket)─► Tarayici
```

---

## Ozellikler

- Gercek zamanli EKG dalga formu (Canvas, 500 Hz)
- Otomatik BPM (kalp hizi) hesaplama
- Lead-off (elektrot kopma) algilama
- Gercekci simulasyon modu (donanim olmadan test)
  - HRV (kalp hizi degiskenligi)
  - Baseline wander (solunum kaynakli)
  - Kas artefakti
  - 50 Hz powerline gurultusu
- Panik atak modu (basili tut → HR yukselir, birak → yavasca normale doner)
- Dark-mode modern arayuz
- ESP32 SSL/WSS destegi (uzak sunucu icin)

---

## Malzeme Listesi

| Parca | Adet | Aciklama |
|-------|------|----------|
| Arduino UNO | 1 | Analog EKG sinyalini okur |
| ESP32 DevKit | 1 | WiFi koprusu (WROOM-32 veya benzeri) |
| AD8232 EKG Modulu | 1 | Kalp sinyali yukseltici |
| 3-Lead EKG Elektrot Kablosu | 1 | AD8232 ile birlikte gelir |
| Tek kullanımlik EKG elektrotlari | 3+ | Yapıskan jelli pad'ler |
| 1K ohm direnc | 1 | Gerilim bolucu icin (onerilen) |
| 2K ohm direnc | 1 | Gerilim bolucu icin (onerilen) |
| Jumper kablolar | ~8 | Baglanti icin |
| USB kablolar | 2 | Arduino + ESP32 besleme |

---

## Proje Yapisi

```
gokhur-ekg/
├── arduino_kodlari/
│   └── ekg_ad8232.ino              # Arduino UNO firmware
├── esp32_firmware/
│   └── esp32_ekg_bridge.ino        # ESP32 WebSocket client firmware
├── webapp/
│   ├── main.py                     # FastAPI backend (WebSocket hub + simulasyon motoru)
│   ├── requirements.txt            # Python bagimliklar
│   └── static/
│       ├── index.html              # Ana sayfa
│       ├── style.css               # Dark-mode stil
│       └── app.js                  # Gercek zamanli EKG cizimi
└── devre_semalari/
    ├── baglanti_semasi.txt         # Tum kablo baglantilari
    └── gerilim_bolucu.txt          # 5V→3.3V donusum detayi
```

---

## Kurulum

### 1. Web Uygulamasi (Backend)

#### Gereksinimler

- Python 3.10+
- pip

#### Adimlar

```bash
# Repoyu klonla
git clone https://github.com/mertcandanzz/gokhur-ekg.git
cd gokhur-ekg/webapp

# Bagimliklari kur
pip install -r requirements.txt

# Sunucuyu baslat
python main.py
```

Sunucu `http://localhost:8000` adresinde ayaga kalkar. Tarayicida ac.

> **Not:** `uvicorn[standard]` paketi WebSocket destegi icin gereklidir. `requirements.txt` bunu icerir ama sorun yasarsan:
> ```bash
> pip install "uvicorn[standard]"
> ```

#### Simulasyon ile Test (Donanim Gerekmez)

1. `http://localhost:8000` adresini tarayicida ac
2. **"Simulasyon"** butonuna tikla → gercekci EKG dalga formu akmaya baslar
3. **"Panik Atak"** butonu belirir → **basili tut** → kalp hizi ~70'ten ~165 BPM'e cikar
4. Butonu **birak** → yaklasik 8 saniyede normale doner

---

### 2. Arduino UNO (AD8232 Sensor)

#### Gereksinimler

- Arduino IDE (1.8+ veya 2.x)

#### Adimlar

1. Arduino IDE'yi ac
2. `arduino_kodlari/ekg_ad8232.ino` dosyasini ac
3. Board: **Arduino UNO** sec
4. Port: Arduino'nun bagili oldugu COM portunu sec
5. **Upload** butonuna bas

#### Kod Ozeti

```cpp
void loop() {
  if (digitalRead(10) == 1 || digitalRead(11) == 1) {
    Serial.println("!");      // Lead-off (elektrot koptu)
  } else {
    Serial.println(analogRead(A0));  // EKG sinyal degeri (0-1023)
  }
  delay(2);  // ~500 Hz ornekleme
}
```

- Baud rate: **115200**
- Lead-off durumunda `!` karakteri gonderir
- Normal durumda 0-1023 arasi analog deger gonderir

---

### 3. ESP32 Firmware

#### Gereksinimler

- Arduino IDE
- ESP32 board desteği (Arduino IDE'de Board Manager'dan kur)
- **WebSockets** kutuphanesi (Markus Sattler / Links2004)

#### Kutuphane Kurulumu

1. Arduino IDE → **Sketch** → **Include Library** → **Manage Libraries**
2. Arama kutusuna `WebSockets` yaz
3. **WebSockets by Markus Sattler** kutuphanesini kur

#### ESP32 Board Kurulumu (ilk kez yapiyorsan)

1. Arduino IDE → **File** → **Preferences**
2. "Additional Board Manager URLs" alanina ekle:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. **Tools** → **Board** → **Board Manager** → `esp32` ara → **esp32 by Espressif Systems** kur
4. Board olarak **ESP32 Dev Module** sec

#### Firmware Yapilandirmasi

`esp32_firmware/esp32_ekg_bridge.ino` dosyasini ac ve su alanlari duzenle:

```cpp
// WiFi bilgilerin
const char* WIFI_SSID     = "WIFI_ADINIZ";      // ← kendi WiFi adin
const char* WIFI_PASSWORD = "WIFI_SIFRENIZ";     // ← kendi WiFi sifren

// FastAPI sunucu adresi
const char* SERVER_HOST = "192.168.1.100";       // ← bilgisayarinin IP'si
const uint16_t SERVER_PORT = 8000;               // ← HTTP icin 8000
const bool USE_SSL = false;                      // ← lokal icin false
```

##### Bilgisayarinin IP'sini Bulma

```bash
# Windows
ipconfig
# IPv4 Address satiri: 192.168.1.XXX

# macOS / Linux
ifconfig | grep "inet "
# veya
ip addr show | grep "inet "
```

##### Lokal Ag vs Uzak Sunucu

| Senaryo | SERVER_HOST | PORT | USE_SSL |
|---------|-------------|------|---------|
| Lokal (ayni WiFi) | `192.168.1.100` | `8000` | `false` |
| Uzak sunucu (HTTP) | `ekg.sunucun.com` | `8000` | `false` |
| Uzak sunucu (HTTPS) | `ekg.sunucun.com` | `443` | `true` |

#### Upload

1. ESP32'yi USB ile bilgisayara bagla
2. Board: **ESP32 Dev Module**
3. Port: ESP32'nin COM portunu sec
4. **Upload** butonuna bas
5. Upload bitince **Serial Monitor** ac (115200 baud) → baglanti durumunu gor

Basarili cikti:
```
=== EKG WebSocket Client ===
WiFi'ye baglaniyor.....
WiFi baglandi! IP: 192.168.1.105
Sunucu: ws://192.168.1.100:8000/ws/device
[WS] Sunucuya baglandi!
```

ESP32 uzerindeki **mavi LED** yaniyorsa sunucuya bagli demektir.

---

### 4. Kablo Baglantilari

#### AD8232 → Arduino UNO

| AD8232 Pin | Arduino Pin |
|------------|-------------|
| OUTPUT | A0 |
| LO+ | D10 |
| LO- | D11 |
| 3.3V | 3.3V |
| GND | GND |

#### Arduino UNO → ESP32

| Arduino Pin | ESP32 Pin |
|-------------|-----------|
| TX (Pin 1) | GPIO16 (RX2) |
| GND | GND |

> **UYARI: Gerilim Bolucusu Onerisi**
>
> Arduino TX pini 5V sinyal cikarir. ESP32 GPIO pinleri 3.3V toleranslidir.
> Direkt baglanti ESP32'ye zarar **verebilir**. Asagidaki direnc devresini kullanmaniz onerilir:
>
> ```
> Arduino TX ──[1K ohm]──┬──► ESP32 GPIO16
>                        │
>                    [2K ohm]
>                        │
>                       GND
>
> Hesap: 5V × 2K / (1K + 2K) = 3.33V
> ```

#### Elektrot Yerlesimleri (3-Lead)

```
        ┌────────────────────────┐
        │                        │
   Kirmizi (RA-)            Sari (LA+)
   Sag omuz/kol             Sol omuz/kol
        │                        │
        │                        │
        │      Yesil (RL/REF)    │
        │      Sag kalca/bacak   │
        │            │           │
        └────────────┴───────────┘
```

| Kablo Rengi | Lead | Konum |
|-------------|------|-------|
| Kirmizi | RA (-) | Sag kol / sag omuza yakin gogus |
| Sari | LA (+) | Sol kol / sol omuza yakin gogus |
| Yesil | RL (REF) | Sag bacak / sag kalca alti |

> **Ipucu:** Elektrotlari yapiskan EKG pad'leri ile cilde yapistirin.
> Cildin kuru ve temiz olmasi sinyal kalitesini arttirir.

---

### 5. Tam Sistem Calistirma (Adim Adim)

```
1. Kablolari baglanti semasina gore yap
2. Elektrotlari yerlestir
3. Arduino UNO'yu USB ile bilgisayara bagla → firmware yukle
4. ESP32'yi USB ile bagla → firmware'daki WiFi/IP ayarlarini duzelt → yukle
5. Bilgisayarda terminali ac:
      cd gokhur-ekg/webapp
      python main.py
6. Tarayicida http://localhost:8000 ac
7. Arduino + ESP32'yi guc kaynaklarina bagla (USB veya powerbank)
8. Birkac saniye icinde "Cihaz Bagli" yazisi ve canli EKG gorunmeli
```

Sorun giderme:

| Belirti | Cozum |
|---------|-------|
| "Cihaz bekleniyor" | ESP32 Serial Monitor'u kontrol et. WiFi veya sunucu IP yanlis olabilir. |
| "ELEKTROT BAGLANTISI YOK" | Elektrotlar duzgun yapistirilmamis veya kablo kopuk. |
| Sinyal cok gurultulu | Elektrot temas kalitesini kontrol et, 50Hz powerline gng. |
| ESP32 LED yanmiyor | WiFi sifresi yanlis veya sunucu IP'si hatali. |
| WebSocket 404 hatasi | `pip install "uvicorn[standard]"` calistir. |

---

## Uzak Sunucuya Deploy

FastAPI backend'i bir VPS veya cloud sunucuya deploy edebilirsin. ESP32 internete baglanarak sunucuya veri gonderir, sen de dunyanin her yerinden EKG izleyebilirsin.

### Caddy ile (otomatik SSL)

```
# /etc/caddy/Caddyfile
ekg.seninsunucun.com {
    reverse_proxy localhost:8000
}
```

```bash
# Sunucuda
cd gokhur-ekg/webapp
pip install -r requirements.txt
python main.py &
sudo systemctl restart caddy
```

### ESP32 Ayarlari (uzak sunucu icin)

```cpp
const char* SERVER_HOST = "ekg.seninsunucun.com";
const uint16_t SERVER_PORT = 443;
const bool USE_SSL = true;
```

---

## Veri Akisi

```
AD8232 Sensor
    │
    │ (analog sinyal)
    ▼
Arduino UNO (A0)
    │
    │ analogRead() → Serial.println() @ 115200 baud
    │
    ▼ (TX pin → GPIO16)
ESP32
    │
    │ Serial2.read() → WebSocket client
    │
    ▼ (WiFi)
FastAPI Backend (:8000)
    │
    │  /ws/device  ← ESP32 veri gonderir
    │  /ws/client  ← Tarayici veri alir
    │
    ▼ (WebSocket broadcast)
Web Tarayici
    │
    ▼
Canvas EKG Grafigi (gercek zamanli)
```

---

## Simulasyon Motoru Detaylari

Simulasyon, AD8232'den gelecek gercek sinyali taklit eder:

| Ozellik | Aciklama |
|---------|----------|
| **PQRST morfolojisi** | Asimetrik P dalgasi, keskin R peak, yuvarlak T dalgasi |
| **HRV** | Her atim suresi %5-8 rastgele degisir (gercek kalp gibi) |
| **Amplitud varyasyonu** | P, R, S, T genlik her atimda %5-15 farklidir |
| **Baseline wander** | 0.2 Hz solunum + 0.05 Hz yavas drift |
| **Kas artefakti** | Rastgele yuksek frekanslı burst'ler |
| **50 Hz powerline** | Hafif sinus dalga girişimi |
| **Panik atak** | HR 70→165 BPM, artan artefakt, ST degisimi, yavas recovery |

---

## Lisans

MIT
