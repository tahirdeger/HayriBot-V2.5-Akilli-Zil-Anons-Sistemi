# 🔔 HayriBot V2.5 — Akıllı Okul Zil ve Anons Sistemi

**HayriBot**, okullar için özel olarak geliştirilmiş, **Telegram üzerinden uzaktan yönetilebilen** ve **Yapay Zeka (TTS)** destekli bir okul otomasyon sistemidir.

Klasik zil programlarının aksine; internet kopsa dahi zilleri çalmaya devam eder ve yazdığınız metinleri doğal Türkçe sesle (Fahrettin Modeli) anons eder.

> 🌐 **Web:** [zamanmakinesi.xyz](https://zamanmakinesi.xyz)

---

## 🚀 Öne Çıkan Özellikler

- **📱 Telegram Entegrasyonu** — Okulun neresinde olursanız zilleri çalın, durdurun, anons yapın veya PC'yi kapatın.
- **🗣️ Yapay Zeka Anons (TTS)** — Yazdığınız metni anında doğal Türkçe sesle seslendirir; sayılar ve saat formatları otomatik okunur.
- **📋 14×3 Zil Planı** — Öğrenci, Öğretmen ve Teneffüs zillerini tek ekranda planlayıp kaydedin.
- **📅 Akıllı Zamanlayıcı** — Telegram bağlantısı olmasa bile ziller zamanında çalar.
- **🚨 Acil Durum Modları** — Tek tuşla Sivil Savunma Sireni, İstiklal Marşı, Saygı Duruşu veya Ezan/Sela.

---

## 🏗️ Sistem Mimarisi

```
main.py ──► Zamanlayıcı (APScheduler)
        ──► Telegram Bot (asyncio thread)
        ──► GUI (Tkinter / gui/app.py)
                └──► MediaManager (VLC)
                └──► TTS Manager (Piper)
```

Uygulama doğrudan `main.py` ile başlar — ayrı bir bekçi/launcher gerekmez.

---

## 🛠️ Kurulum (Kaynak Koddan)

**Gereksinimler:** Python 3.11, VLC Media Player (64-bit sistem geneli kurulum)

```bash
git clone https://github.com/tahirdeger/HayriBot-V2.5-Akilli-Zil-Anons-Sistemi.git
cd HayriBot-V2.5-Akilli-Zil-Anons-Sistemi

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**TTS modellerini indirin** ([Piper Releases](https://github.com/rhasspy/piper/releases)) ve `models/` klasörüne koyun:
```
models/
  tr_TR-fahrettin-medium.onnx
  tr_TR-fahrettin-medium.onnx.json
```

**Başlatın:**
```bash
python main.py
```

---

## 🔑 İlk Ayarlar: Telegram Bot

1. Telegram'da **@BotFather** → `/newbot` → Token'ı alın.
2. **@userinfobot** → kendi Kullanıcı ID'nizi alın.
3. HayriBot arayüzünde **⚙ Sistem Ayarları** → API Key + Kullanıcı ID → **Kaydet**.
4. Program yeniden başlar; telefondan `/start` yazın.

---

## 📖 Kullanım

### Zil Ekleme (GUI)
Sağ paneldeki **14×3 grid**'e zil saatlerini girin (format: `08:30`) ve **💾 Kaydet**'e tıklayın. Boş satırlar atlanır.

### Sesli Anons
Sol panelde **📢 Duyuru** alanına metin yazın → **▶️ Seslendir**.  
_(TTS modeli yüklenirken buton devre dışıdır; ⏳ etiketi yeşile döndüğünde kullanılabilir.)_

### Telegram Komutları

| Komut / Buton | Açıklama |
|---|---|
| `🔔 Öğrenci` / `👩🏫 Öğretmen` | Zil çal |
| `📢 Duyuru` → metin yaz | Sesli anons |
| `⏹️ Tümünü Durdur` | Çalan sesi durdur |
| `🔔 Zil Yönet` | Zil listesi, açma/kapama |
| `🖥️ Kapat` | Bilgisayarı kapat (onaylı) |
| `ℹ️ Durum` | CPU / bellek durumu |

---

## 📦 EXE Derleme

```bash
# Sanal ortamı aktifleştirin
.venv\Scripts\activate

# Derleyin
pyinstaller HayriBot.spec --clean --noconfirm
```

Çıktı: `dist\HayriBot\HayriBot.exe`

> `dlls\` klasöründeki VLC DLL'leri ve `models\` içindeki ONNX dosyaları spec aracılığıyla otomatik dahil edilir.

---

## 📂 Proje Yapısı

```
HayriBot/
├── main.py               # Giriş noktası
├── HayriBot.spec         # PyInstaller yapılandırması
├── requirements.txt
├── config/               # MediaManager, TTS_SETTINGS
├── data/                 # SQLite DB (otomatik oluşur, .gitignore'da)
├── gui/                  # Tkinter arayüzü
├── handlers/             # Telegram komut işleyicileri
├── hooks/                # PyInstaller hook'ları
├── media/                # Zil ve anons ses dosyaları
├── models/               # Piper ONNX modelleri (.gitignore'da)
└── utils/                # DB, TTS, Scheduler, Helpers
```

---

## 🤝 Katkıda Bulunma

1. Repoyu fork'layın.
2. Yeni bir dal açın: `git checkout -b feature/yeni-ozellik`
3. Değişikliklerinizi yapın ve commit edin.
4. Pull Request gönderin.

---

*Geliştirici: **Tahir Değer** | [zamanmakinesi.xyz](https://zamanmakinesi.xyz)*
