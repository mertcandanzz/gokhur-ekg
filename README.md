# Gokhur EKG

AD8232 EKG sensoru ile gercek zamanli kalp ritmi izleme sistemi.

Arduino UNO kalp sinyalini okur, ESP32 WiFi uzerinden bilgisayardaki FastAPI sunucusuna iletir, tarayicidaki dark-mode web arayuzu canli EKG grafigi cizer.

```
Kalp → AD8232 → Arduino UNO → ESP32 → WiFi → FastAPI → Tarayici
```

---

## Ne Yapabilirsin?

- Kendi kalbinin gercek zamanli EKG'sini tarayicidan izle
- BPM (kalp hizi) otomatik hesaplanir
- Elektrot koparsa ekranda uyari cikar
- Donanim olmadan simulasyon moduyla test et (gercekci PQRST dalga formu)
- Panik atak simule et (basili tut → HR yukselir, birak → yavasca normale doner)

---

## Malzeme Listesi

Projeyi hayata gecirmek icin su parcalara ihtiyacin var:

| Parca | Adet | Not |
|-------|------|-----|
| Arduino UNO (veya klon) | 1 | Kalp sinyalini okuyan ana kart |
| ESP32 DevKit v1 | 1 | WiFi ile internete/sunucuya baglanir. WROOM-32 modelli herhangi bir ESP32 olur |
| AD8232 EKG Modulu | 1 | Kalp elektrik sinyalini yukseltip Arduino'ya veren modul |
| 3-Lead EKG Elektrot Kablosu | 1 | Genelde AD8232 ile birlikte gelir (3.5mm jack'li, 3 renkli kablo) |
| Tek kullanimlik EKG pad'leri | 3+ | Yapiskan jelli elektrot padleri. Eczaneden veya internetten alinir |
| Breadboard | 1 | Kablo baglantilari icin |
| Erkek-erkek jumper kablo | ~8 | Breadboard baglantilari icin |
| 1K ohm direnc | 1 | Gerilim bolucu icin (onerilen, zorunlu degil) |
| 2K ohm direnc | 1 | Gerilim bolucu icin (onerilen, zorunlu degil) |
| Micro-USB kablo | 2 | Arduino + ESP32'yi bilgisayara/guc kaynagina baglamak icin |

> **Direnc olmadan da calisir mi?** Evet, cogu ESP32 kartinda 5V sinyal tolere edilir ve sorunsuz calisir. Ama uzun vadede ESP32'ye zarar verme riski vardir. 1K + 2K direncle gerilim bolucusu yapmak en guvenli yoldur. Detayi asagida anlattim.

---

## Baslangic: Oncelikle Donanim Olmadan Test Et

Projeyi ilk kez calistirirken **hicbir donanima ihtiyacin yok**. Sadece bilgisayarinla simulasyon modunu deneyebilirsin.

### Adim 1: Python Kur

Bilgisayarinda Python yoksa:

- **Windows:** https://www.python.org/downloads/ adresinden indir. Kurulum sirasinda **"Add Python to PATH"** kutucugunu isaretlemeyi unutma.
- **macOS:** `brew install python3` veya python.org'dan indir.
- **Linux:** `sudo apt install python3 python3-pip`

Kurulumu dogrula:
```bash
python --version
# Python 3.10+ cikmalı
```

### Adim 2: Projeyi Indir

```bash
git clone https://github.com/mertcandanzz/gokhur-ekg.git
cd gokhur-ekg
```

Git yoksa GitHub'dan **Code → Download ZIP** ile indirip cikar.

### Adim 3: Bagimliklari Kur

```bash
cd webapp
pip install -r requirements.txt
```

> **Hata alirsan:** `pip install "uvicorn[standard]"` komutunu ayrica calistir. Bu paket WebSocket destegi saglar.

### Adim 4: Sunucuyu Baslat

```bash
python main.py
```

Terminalde su ciktiyi gormeli sin:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Adim 5: Tarayicida Ac

Tarayicini ac ve adres cubuguna yaz:
```
http://localhost:8000
```

Siyah bir ekran, grid cizgileri ve "Cihaz baglantisi bekleniyor" yazisi gormelisin.

### Adim 6: Simulasyonu Baslat

1. Sag ustteki **"Simulasyon"** butonuna tikla
2. Birka saniye icinde gercekci bir EKG dalga formu akmaya baslar
3. Sol ustte **BPM** (kalp hizi) gorunur (~70 BPM civari)
4. **"Panik Atak"** butonu belirir. **Basili tut** → kalp hizi yukselir, sinyal kirmiziya doner. **Birak** → 8 saniyede normale doner.

Bu kadar! Simdi donanima gecebiliriz.

---

## Donanim Kurulumu (Adim Adim)

### Genel Bakis

Sistemde 3 donanim var. Her birinin ne is yaptigini anlamak onemli:

```
┌─────────────┐     ┌──────────────┐     ┌─────────┐
│   AD8232    │────►│ Arduino UNO  │────►│  ESP32  │
│  EKG Modul  │     │              │     │         │
│             │     │ Kalp sinyalini│     │ Seri    │
│ Kalp sinyal.│     │ dijitale     │     │ veriyi  │
│ yukseltir   │     │ cevirir      │     │ WiFi ile│
│             │     │              │     │ gonderir│
└─────────────┘     └──────────────┘     └─────────┘
   analog out          A0'dan okur         Serial2
   LO+, LO-           TX'ten yazar       ile okur
                                          WebSocket
                                          ile iletir
```

---

### Adim 1: AD8232'yi Arduino'ya Bagla

AD8232 modulunun **5 pini** var. Bunlari Arduino UNO'ya baglayacaksin.

**Breadboard uzerinde:**

```
AD8232 Modul              Arduino UNO
────────────              ───────────
  GND  ──────────────────── GND
  3.3V ──────────────────── 3.3V
  OUTPUT ────────────────── A0
  LO+  ──────────────────── D10
  LO-  ──────────────────── D11
```

Tablo halinde:

| AD8232 Pini | Arduino Pini | Aciklama |
|-------------|-------------|----------|
| GND | GND | Ortak toprak |
| 3.3V | 3.3V | AD8232'nin guc beslemesi. **5V BAGLAMA**, modul 3.3V ile calisir |
| OUTPUT | A0 | EKG analog sinyal cikisi |
| LO+ | D10 | Lead-off algilama (+ elektrot koptu mu?) |
| LO- | D11 | Lead-off algilama (- elektrot koptu mu?) |

**Breadboard'da nasil gorunur:**

```
Breadboard
──────────────────────────────────────────────
│                                            │
│  AD8232          Jumper          Arduino    │
│  ┌─────┐        kablolar        ┌───────┐  │
│  │ GND ├────── siyah ──────────►│ GND   │  │
│  │ 3.3V├────── kirmizi ────────►│ 3.3V  │  │
│  │ OUT ├────── sari ───────────►│ A0    │  │
│  │ LO+ ├────── yesil ─────────►│ D10   │  │
│  │ LO- ├────── mavi ──────────►│ D11   │  │
│  └─────┘                        └───────┘  │
│                                            │
──────────────────────────────────────────────
```

> **Dikkat:** AD8232'yi **3.3V** pinine bagla, 5V degil. 5V modulu yakabilir.

---

### Adim 2: Arduino'yu ESP32'ye Bagla

Arduino, okudugi EKG verisini seri port (TX pini) uzerinden gonderir. ESP32 bunu GPIO16 (RX2) pininden okur.

**Sadece 2 kablo:**

| Arduino Pini | ESP32 Pini | Aciklama |
|-------------|-----------|----------|
| TX (Pin 1) | GPIO16 (RX2) | Arduino'nun gonderdigi veri ESP32'ye gider |
| GND | GND | **Ortak toprak sart!** Yoksa veri okunamaz |

**Breadboard'da:**

```
Arduino UNO                    ESP32
┌──────────┐                  ┌──────────┐
│          │                  │          │
│  TX (1)  ├────── beyaz ────►│ GPIO16   │
│          │                  │          │
│  GND     ├────── siyah ────►│ GND      │
│          │                  │          │
└──────────┘                  └──────────┘
```

#### Gerilim Bolucusu (Onerilen)

Arduino TX pini **5V** sinyal cikarir. ESP32 ise **3.3V** ile calisir.

**Direnc olmadan:** Cogu zaman calisir ama ESP32'ye zarar verebilir.

**Direncle (guvenli yol):**

```
Arduino TX ────[1K ohm]────┬────► ESP32 GPIO16 (RX2)
                           │
                       [2K ohm]
                           │
                          GND
```

Breadboard uzerinde:

```
Arduino TX pin
      │
      ▼
 ┌────┤ 1K direnc ├────┐
 │                      ├────► ESP32 GPIO16'ya jumper
 │                      │
 │                 ┌────┤ 2K direnc ├────┐
 │                 │                      │
 │                 │                     GND
```

Formul: `5V × 2K / (1K + 2K) = 3.33V` → ESP32 icin guvenli.

> **2K direncin yoksa:** 2 tane 1K direnci seri baglayarak 2K elde edebilirsin.

---

### Adim 3: Elektrotlari Yerlestir

AD8232 modulune 3.5mm jack ile baglanan 3 renkli kablo vardir. Her birinin ucuna yapiskan EKG pad'i takip vucuda yapistirilir.

**Kablo renkleri ve konumlari:**

| Renk | Lead Adi | Nereye Yapistirılir |
|------|----------|---------------------|
| Kirmizi | RA (Right Arm) | **Sag gogus** — sag omuzun hemen altinda, koprucuk kemiginin 2-3 cm asagisi |
| Sari | LA (Left Arm) | **Sol gogus** — sol omuzun hemen altinda, koprucuk kemiginin 2-3 cm asagisi |
| Yesil | RL (Right Leg / REF) | **Sag karin** — en alt kaburga kemiginin altinda, sag taraf |

Vucuttaki konumlar:

```
         Sag omuz              Sol omuz
            ▼                     ▼
       ● Kirmizi              ● Sari
       (RA -)                 (LA +)
            \                   /
             \                 /
              \     Kalp      /
               \     ♥       /
                \           /
                 \         /
                  \       /
                   \     /
                    \   /
                ● Yesil
                (RL / REF)
                Sag karin alt
```

**Onemli ipuclari:**

- Elektrot yapistirmadan once cildi **kuru bez** ile silin (yag ve ter sinyal kalitesini dusurur)
- Pad'lerin yapiskan tarafi cilde temas etmeli
- Elektrotlari **kemik uzerine degil**, kasta et olan bölgeye yapistir
- Hareket etme — kas hareketi sinyal e gurultu ekler
- AD8232'nin jack girisine kabloyu tam oturttugundan emin ol

---

### Adim 4: Arduino'ya Firmware Yukle

1. Bilgisayarinda **Arduino IDE** yoksa indir: https://www.arduino.cc/en/software

2. Arduino UNO'yu **USB kabloyla** bilgisayara bagla

3. Arduino IDE'yi ac

4. **File → Open** ile `arduino_kodlari/ekg_ad8232.ino` dosyasini ac

5. Ust menudan ayarlari yap:
   - **Tools → Board → Arduino AVR Boards → Arduino Uno**
   - **Tools → Port →** Arduino'nun bagili oldugu portu sec (Windows'ta `COM3`, `COM4` gibi gorunur. Mac'te `/dev/cu.usbmodem...`)

   > Port gorunmuyorsa: USB kabloyu cikart-tak, farkli USB girisini dene. Klon Arduino kullaniyorsan CH340 driverini kurmak gerekebilir: https://sparks.gogo.co.nz/ch340.html

6. Sol ustteki **ok (→) butonuna** bas (Upload)

7. Altta **"Done uploading"** yazisini bekle

**Kodun ne yaptigi:**

```cpp
void setup() {
  Serial.begin(115200);        // ESP32 ile ayni hizda haberles
  pinMode(10, INPUT);          // LO+ pini (lead-off algilama)
  pinMode(11, INPUT);          // LO- pini (lead-off algilama)
}

void loop() {
  if (digitalRead(10) == 1 || digitalRead(11) == 1) {
    Serial.println("!");       // Elektrot kopuk → "!" gonder
  } else {
    Serial.println(analogRead(A0));  // EKG degerini oku (0-1023 arasi)
  }
  delay(2);                    // 2ms bekle → saniyede ~500 okuma
}
```

- `analogRead(A0)`: AD8232'den gelen analog sinyali 0-1023 arasi dijital degere cevirir
- `digitalRead(10)` ve `digitalRead(11)`: Elektrot kopuk mu kontrol eder
- Tum veri seri porttan (TX pini) gonder ilir → ESP32 bunu okur

> **Test:** Upload'dan sonra **Tools → Serial Monitor** ac, baud rate'i **115200** yap. Rakamlar akiyorsa Arduino dogru calisiyor. Elektrotlar yoksa `!` goreceksin.

---

### Adim 5: ESP32'ye Firmware Yukle

Bu adim biraz daha uzun cunku ESP32 icin ek ayarlar gerekiyor.

#### 5a. Arduino IDE'ye ESP32 Destegi Ekle

1. Arduino IDE'de **File → Preferences** ac
2. **"Additional Board Manager URLs"** kutusuna su URL'yi yapistir:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
   (Zaten baska URL varsa virgul ile ayir)
3. **OK** tikla
4. **Tools → Board → Board Manager** ac
5. Arama kutusuna `esp32` yaz
6. **"esp32 by Espressif Systems"** kutuphanesini bul ve **Install** tikla (indirmesi birka dakika surebilir)

#### 5b. WebSockets Kutuphanesini Kur

1. **Sketch → Include Library → Manage Libraries** ac
2. Arama kutusuna `WebSockets` yaz
3. **"WebSockets by Markus Sattler"** bul ve **Install** tikla

#### 5c. WiFi ve Sunucu Ayarlarini Duzelt

`esp32_firmware/esp32_ekg_bridge.ino` dosyasini Arduino IDE'de ac.

Dosyanin basindaki su satirlari **kendi bilgilerinle** degistir:

```cpp
// ---- WiFi Ayarlari ----
const char* WIFI_SSID     = "WIFI_ADINIZ";      // ← evdeki WiFi'nin adi
const char* WIFI_PASSWORD = "WIFI_SIFRENIZ";     // ← WiFi sifresi

// ---- FastAPI Sunucu Ayarlari ----
const char* SERVER_HOST = "192.168.1.100";       // ← bilgisayarinin yerel IP'si
const uint16_t SERVER_PORT = 8000;               // ← 8000 (degistirme)
const bool USE_SSL = false;                      // ← false (lokal icin)
```

**Bilgisayarinin IP'sini bulma:**

Windows'ta:
```
1. Windows + R tusla
2. "cmd" yaz, Enter
3. ipconfig yaz, Enter
4. "IPv4 Address" satirindaki numarayi al (ornek: 192.168.1.42)
```

Mac/Linux'ta:
```bash
ifconfig | grep "inet "
# veya
ip addr show | grep "inet "
```

> **Onemli:** ESP32 ve bilgisayarin **ayni WiFi aginda** olmali. Bilgisayar ethernet'e bagliysa ve ESP32 WiFi'ye bagliysa, ayni router'a baglilarsa calisir.

#### 5d. Upload

1. ESP32'yi USB ile bilgisayara bagla (Arduino'yu cikarmana gerek yok, farkli USB girisi kullan)
2. Arduino IDE'de:
   - **Tools → Board → esp32 → ESP32 Dev Module**
   - **Tools → Port →** ESP32'nin portunu sec (Arduino'nunkinden farkli bir COM numarasi olacak)
3. **Upload (→)** butonuna bas
4. ESP32 uzerinde **BOOT** butonu varsa, "Connecting..." yazisini gordugunde BOOT butonuna bir kez bas (bazi kartlarda gerekir)
5. **"Done uploading"** bekle

#### 5e. Baglantıyı Dogrula

Upload bittikten sonra **Tools → Serial Monitor** ac (baud: **115200**).

**Basarili cikti:**
```
=== EKG WebSocket Client ===
WiFi'ye baglaniyor.....
WiFi baglandi! IP: 192.168.1.105
Sunucu: ws://192.168.1.42:8000/ws/device
[WS] Sunucuya baglandi!
```

**Sorun varsa:**

| Serial Monitor'de | Anlami | Cozum |
|-------------------|--------|-------|
| `WiFi'ye baglaniyor...........` (cok uzun) | WiFi'ye baglanamadi | SSID ve sifre yanlis. Buyuk/kucuk harf duyarli! |
| `WiFi baglandi` ama `[WS] Sunucu baglantisi kesildi` | WiFi OK ama sunucuya ulasamiyor | `python main.py` calistigini ve IP adresini kontrol et |
| Hicbir sey yazmiyor | ESP32 firmware yuklenmemis | Upload'u tekrarla, BOOT butonunu dene |

---

### Adim 6: Her Seyi Birlestir ve Calistir

Artik her sey hazir. Sirayla:

**1) Bilgisayarinda sunucuyu baslat:**
```bash
cd gokhur-ekg/webapp
python main.py
```

**2) Tarayicida ac:**
```
http://localhost:8000
```
Ekranda "Cihaz bekleniyor" yazmali.

**3) Arduino'yu guc kaynagina bagla:**
- USB ile bilgisayara
- veya USB ile powerbank'e/sarj adaptorune

**4) ESP32'yi guc kaynagina bagla:**
- USB ile bilgisayardaki diger porta
- veya USB ile powerbank'e

**5) 5-10 saniye bekle:**
- ESP32 uzerindeki mavi LED yanarsa → sunucuya baglandi
- Tarayicida "Cihaz Bagli" yazisi cikar
- EKG dalga formu akmaya baslar
- BPM hesaplanir

> **Elektrot kopuk uyarisi aliyorsan:** Pad'lerin ciltte iyi yapistirdigini, jack'in AD8232'ye tam oturdugunu kontrol et.

---

## Proje Yapisi

```
gokhur-ekg/
├── arduino_kodlari/
│   └── ekg_ad8232.ino              # Arduino UNO firmware
├── esp32_firmware/
│   └── esp32_ekg_bridge.ino        # ESP32 WebSocket client firmware
├── webapp/
│   ├── main.py                     # FastAPI backend + simulasyon motoru
│   ├── requirements.txt            # Python bagimliliklari
│   └── static/
│       ├── index.html              # Web arayuzu
│       ├── style.css               # Dark-mode tasarim
│       └── app.js                  # Gercek zamanli EKG cizimi
└── devre_semalari/
    ├── baglanti_semasi.txt         # Detayli kablo baglantilari (ASCII)
    └── gerilim_bolucu.txt          # 5V→3.3V direnc hesaplari
```

---

## Sorun Giderme

### Web Arayuzu

| Sorun | Cozum |
|-------|-------|
| Sayfa acilmiyor | `python main.py` calistigini kontrol et. Terminalde hata var mi bak |
| "Sunucuya baglaniliyor" surekli | Sayfa WebSocket baglantisi kuramadi. Tarayicida F12 → Console'a bak |
| Simulasyon butonu calismıyor | `pip install "uvicorn[standard]"` calistir, sunucuyu yeniden baslat |
| "Cihaz bekleniyor" surekli | ESP32 bagli degil veya sunucu IP'si yanlis |
| EKG cizgisi duz | Elektrotlar dogru yapismamis veya AD8232 baglantisi hatali |
| BPM hesaplanmiyor | Sinyal cok zayif veya cok gurultulu. Elektrot temassini iyilestir |

### Arduino

| Sorun | Cozum |
|-------|-------|
| Upload basarisiz | Dogru Board (Arduino Uno) ve dogru Port secili mi? |
| Serial Monitor'de garip karakterler | Baud rate'i **115200** yap |
| Surekli `!` yaziyor | Elektrot takili degil veya LO+/LO- kablo baglantisi hatali |
| Hep ayni deger (ornegin 1023) | AD8232 OUTPUT → A0 baglantisini kontrol et |

### ESP32

| Sorun | Cozum |
|-------|-------|
| Upload basarisiz ("Connecting..." surekli) | BOOT butonuna basili tutarak upload'u baslat, "Connecting..." gozuktiginde birak |
| `WiFi baglantisi basarisiz` | SSID ve sifre buyuk/kucuk harf duyarli. Cift tirnak icinde ozel karakter varsa dikkat |
| WiFi OK ama `[WS] Sunucu baglantisi kesildi` | Bilgisayarinda `python main.py` calisiyor mu? IP adresi dogru mu? Firewall WebSocket'i engelliyor olabilir |
| LED yanmiyor | Upload basarili mi kontrol et. WiFi bilgilerini kontrol et |

### Donanim

| Sorun | Cozum |
|-------|-------|
| Sinyal cok gurultulu / titriyor | Elektrot temas kalitesi dusuk. Cildi temizleyip yeni pad dene. Hareketsiz dur |
| Duz cizgi (sinyal yok) | AD8232 → Arduino kablolarini kontrol et. 3.3V ve GND bagli mi? |
| Arduino'dan veri geliyor ama ESP32'de yok | Arduino TX → ESP32 GPIO16 baglantisini kontrol et. GND ortak mi? |
| Sinyal var ama ters gorunuyor | Kirmizi ve sari elektrotlarin yerini degistir |

---

## Uzak Sunucuya Deploy (Opsiyonel)

Projeyi bir VPS'e deploy edersen, ESP32 internete baglanip dunyanin her yerinden EKG izleyebilirsin.

### Sunucuda Kurulum

```bash
# Sunucuya baglan
ssh kullanici@sunucu-ip

# Projeyi klonla
git clone https://github.com/mertcandanzz/gokhur-ekg.git
cd gokhur-ekg/webapp

# Kur ve baslat
pip install -r requirements.txt
python main.py &
```

### Caddy ile HTTPS (Otomatik SSL Sertifikasi)

```
# /etc/caddy/Caddyfile
ekg.senindomain.com {
    reverse_proxy localhost:8000
}
```

```bash
sudo systemctl restart caddy
```

Caddy otomatik olarak Let's Encrypt'ten SSL sertifikasi alir. WebSocket da otomatik proxy'lenir.

### ESP32 Ayarlari (Uzak Sunucu)

```cpp
const char* SERVER_HOST = "ekg.senindomain.com";
const uint16_t SERVER_PORT = 443;
const bool USE_SSL = true;
```

---

## Veri Akisi Diyagrami

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ♥ Kalp                                                      │
│    │                                                         │
│    ▼ (elektriksel sinyal, mikrovolt seviyesinde)              │
│                                                              │
│  AD8232 EKG Modulu                                           │
│    │ Sinyali yukseltir, filtreler                            │
│    │ OUTPUT pininden 0-3.3V analog cikis verir               │
│    ▼                                                         │
│                                                              │
│  Arduino UNO                                                 │
│    │ A0 pininden analogRead() ile okur (0-1023 dijital)      │
│    │ Serial.println() ile TX pininden seri veri gonderir     │
│    │ Baud rate: 115200, saniyede ~500 okuma                  │
│    ▼                                                         │
│                                                              │
│  ESP32                                                       │
│    │ GPIO16 (RX2) pininden Serial2 ile seri veriyi okur      │
│    │ WiFi'ye baglanir                                        │
│    │ WebSocket client olarak FastAPI sunucusuna baglanir      │
│    │ Okunan veriyi 20ms aralikla toplu gonderir              │
│    ▼                                                         │
│                                                              │
│  FastAPI Sunucu (bilgisayar veya VPS)                        │
│    │ /ws/device  ← ESP32 buraya baglanir, veri gonderir      │
│    │ /ws/client  ← Tarayici buraya baglanir, veri alir       │
│    │ Gelen veriyi tum bagli tarayicilara broadcast eder      │
│    ▼                                                         │
│                                                              │
│  Web Tarayici                                                │
│    Canvas uzerinde gercek zamanli EKG grafigi cizer          │
│    BPM hesaplar, lead-off algilar                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Simulasyon Motoru Detaylari

Donanim olmadan test edebilmek icin backend'de gercekci bir EKG simulasyon motoru var. AD8232'den gelecek sinyalin ozelliklerini taklit eder:

| Ozellik | Ne Yapar | Neden Onemli |
|---------|----------|--------------|
| **PQRST morfolojisi** | Her atimda P, Q, R, S, T dalgalarini uretir. P asimetrik, R keskin, T yumusak | Gercek kalp sinyali boyle gorunur |
| **HRV (Heart Rate Variability)** | Her atim suresi %5-8 rastgele degisir | Gercek kalpte her atim biraz farklidir |
| **Amplitud varyasyonu** | P, R, S, T genlikleri her atimda %5-15 farkli | Biyolojik sinyal hic sabit degildir |
| **Baseline wander** | 0.2 Hz solunum dalgalanmasi + 0.05 Hz yavas drift | Nefes alip verme sinyali kaydiririr |
| **Kas artefakti** | Rastgele yuksek frekanslı gurultu patlamalari | Hareket edince sensorden boyle sinyal gelir |
| **50 Hz powerline** | Hafif sinus dalga girisimi | Sebekeden gelen elektrik gurultusu |
| **Panik atak modu** | HR 70→165 BPM, daha fazla artefakt, ST degisimi, yavas recovery | Stres altindaki kalbi simule eder |

---

## Lisans

MIT
