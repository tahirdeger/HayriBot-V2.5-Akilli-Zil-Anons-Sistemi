# 📘 HayriBot V2.5 - Proje Teknik Özeti ve Hafıza Kartı

Bu belge, HayriBot projesinin mimarisini, bileşenlerini ve uygulanan kritik kararlılık yamalarını özetler. İlerideki geliştirmeler için referans niteliğindedir.

---

## 🏗️ Sistem Mimarisi

Proje, **Python** tabanlı, **Tkinter** arayüzlü, **Telegram** entegrasyonlu ve **Yapay Zeka (TTS)** destekli bir okul otomasyon sistemidir.

### 🔄 Çalışma Döngüsü

1. **Main (`main.py`):** Uygulamanın tek giriş noktası.
   - Kilit dosyası (`app.lock`) kontrolü ve temizliği yapar.
   - Veritabanını başlatır.
   - Zamanlayıcıyı Telegram'dan **bağımsız** başlatır (bot token olmasa da ziller çalar).
   - Telegram Botunu (`asyncio` thread) başlatır.
   - GUI'yi (`gui/app.py`) başlatır.
2. **GUI (`gui/app.py`):** Kullanıcı arayüzü. Olayları (Event) dinler ve `MediaManager`'ı yönetir.
3. **Medya Yöneticisi (`config/settings.py`):** Ses çalma işlemlerinin merkezi. VLC kütüphanesini kullanır.

---

## 📂 Kritik Dosyalar ve Görevleri

| Dosya | Görev |
| :--- | :--- |
| **`main.py`** | Başlatıcı, Loglama, Kilit Temizliği, Zamanlayıcı, Bot ve GUI Thread Yönetimi. |
| **`gui/app.py`** | Tkinter Arayüzü, 14×3 Zil Grid, TTS Durum Etiketi, Başlangıç Isıtma. |
| **`config/settings.py`** | **`MediaManager` Sınıfı.** VLC Instance yönetimi, Ses çalma/durdurma, Meşguliyet kontrolü. |
| **`utils/tts_manager.py`** | **Piper TTS** entegrasyonu. Türkçe metin önişleme (sayı→kelime), gecikmeli yükleme. |
| **`handlers/command_handlers.py`** | Telegram komutları (`/start`, `/volume`, `/pckapat` vb.) ve mesaj işleme. |
| **`utils/scheduler.py`** | APScheduler ile zil saatlerini planlar ve tetikler. |
| **`utils/event_emitter.py`** | Bileşenler arası (Bot ↔ GUI ↔ Media) haberleşmeyi sağlayan olay veriyolu. |

---

## 🛠️ Uygulanan Kritik Yamalar ve Çözümler

### 1. Ses Sistemi Çökmesi (Access Violation 0xC0000005)
- **Sorun:** VLC `MediaPlayer` nesnelerinin sürekli oluşturulup silinmesi bellek hatasına yol açıyordu.
- **Çözüm:** `vlc.Instance` tek bir kez oluşturulup (`self.vlc_instance`) tüm uygulama boyunca saklandı.

### 2. Zamanlayıcı Telegram'a Bağımlıydı
- **Sorun:** Bot token yoksa veya internet kesilmişse ziller hiç çalmıyordu.
- **Çözüm (`main.py`):** `baslat_zamanlayici()` coroutine'i `start_telegram_bot_async()`'dan önce çalışacak şekilde ayrıldı.

### 3. VLC Başlatma Bloğu
- **Sorun:** `time.sleep(1.0)` her zil çalmada 1 saniyelik thread bloğuna yol açıyordu.
- **Çözüm (`config/settings.py`):** Sleep yerine VLC state polling döngüsü eklendi.

### 4. PyInstaller `_internal` Dizin Sorunu
- **Sorun:** PyInstaller 6.x her şeyi `_internal/` altına koyar; `path_resolver.py` EXE yanında arar.
- **Çözüm (`HayriBot.spec`):** `contents_directory='.'` ile `_internal` kaldırıldı, tüm dosyalar EXE yanına çıktı.

### 5. TTS Model Anahtarı Uyumsuzluğu
- **Sorun:** DB'de `"male"/"female"` tutulurken UI `"ERKEK-Fahrettin"` gösteriyor; model yüklenemiyordu.
- **Çözüm (`tts_manager.py`):** `load_model()` başında normalize dict eklendi.

### 6. TTS Yüklenme Bildirimi Yoktu
- **Sorun:** Kullanıcı model yüklenmeden anons butonuna basıyor, sessiz hata alıyordu.
- **Çözüm (`gui/app.py`):** `_poll_tts_status()` ile Duyuru paneline durum etiketi eklendi; yüklenene kadar buton devre dışı.

---

## 🆕 V2.5 Yeni Özellikler

### 14×3 Inline Zil Grid
Eski dialog/tablo sistemi kaldırıldı. Sağ panele doğrudan 14 satır × 3 sütun (Öğrenci / Öğretmen / Teneffüs) grid yerleştirildi. Kullanıcı saatleri yazıp **Kaydet** der, sistem tümünü siler ve yeniden yükler.

### Türkçe Metin Önişlemcisi
`tts_manager._preprocess()` ile senteze girmeden:
- Saat formatı: `08:30` → "sekiz otuz"
- Sayılar (0–999): `"15 dakika"` → `"on beş dakika"`
- Çoklu boşluk/nokta temizlenir

---

## ⚙️ Teknik Özellikler

| Bileşen | Teknoloji |
| :--- | :--- |
| Dil | Python 3.11 |
| GUI | Tkinter + ttk |
| Ses Motoru | `python-vlc` |
| TTS | `piper-tts` (ONNX, çevrimdışı, Fahrettin medium) |
| Veritabanı | SQLite (`data/zil_db.sqlite`) |
| Zamanlayıcı | `APScheduler` BackgroundScheduler |
| Bot | `python-telegram-bot` (Async) |
| Derleme | `PyInstaller 6.x` (`contents_directory='.'`) |

---

## 📝 Geliştirici Notları

**Derleme:**
```bash
pyinstaller HayriBot.spec --clean --noconfirm
```

**Ses Dosyaları:** `media/` klasöründeki dosya isimleri kod içinde sabittir. Değiştirirken isimler korunmalıdır.

**TTS Modelleri:** `models/` klasörüne `tr_TR-fahrettin-medium.onnx` ve `.onnx.json` dosyaları elle kopyalanmalıdır (.gitignore ile hariç tutulmuştur).

**Git:** Hassas veriler (`zil_db.sqlite`, `*.log`, `dlls/`, `models/*.onnx`) `.gitignore` ile hariç tutulmuştur.

---

*Geliştirici: Tahir Değer | [zamanmakinesi.xyz](https://zamanmakinesi.xyz)*
