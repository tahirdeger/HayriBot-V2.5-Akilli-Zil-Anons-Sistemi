# 📘 HayriBot V2.5 - Proje Teknik Özeti ve Hafıza Kartı

Bu belge, HayriBot projesinin mimarisini, bileşenlerini ve uygulanan kritik kararlılık yamalarını özetler. İlerideki geliştirmeler için referans niteliğindedir.

---

## 🏗️ Sistem Mimarisi

Proje, **Python** tabanlı, **Tkinter** arayüzlü, **Telegram** entegrasyonlu ve **Yapay Zeka (TTS)** destekli bir okul otomasyon sistemidir. Sistem, çökme korumalı (Watchdog) bir yapı üzerinde çalışır.

### 🔄 Çalışma Döngüsü
1.  **Launcher (`launcher.py`):** Bekçi görevi görür. `main.py`'yi başlatır ve izler. Çökme durumunda yeniden başlatır.
2.  **Main (`main.py`):** Uygulamanın giriş noktasıdır.
    *   Kilit dosyası (`app.lock`) kontrolü ve temizliği yapar.
    *   Veritabanını başlatır.
    *   Telegram Botunu (`asyncio` thread) başlatır.
    *   GUI'yi (`gui/app.py`) başlatır.
3.  **GUI (`gui/app.py`):** Kullanıcı arayüzü. Olayları (Event) dinler ve `MediaManager`'ı yönetir.
4.  **Medya Yöneticisi (`config/settings.py`):** Ses çalma işlemlerinin merkezi. VLC kütüphanesini kullanır.

---

## 📂 Kritik Dosyalar ve Görevleri

| Dosya | Görev |
| :--- | :--- |
| **`main.py`** | Başlatıcı, Loglama, Kilit Temizliği, Bot ve GUI Thread Yönetimi. |
| **`gui/app.py`** | Tkinter Arayüzü, Butonlar, Liste Yönetimi, Başlangıç Isıtma (Warmup). |
| **`config/settings.py`** | **`MediaManager` Sınıfı.** VLC Instance yönetimi, Ses çalma/durdurma, Meşguliyet kontrolü. |
| **`utils/tts_manager.py`** | **Piper TTS** entegrasyonu. Metni sese çevirir. Gecikmeli yükleme (Lazy Loading) yapar. |
| **`handlers/command_handlers.py`** | Telegram komutları (`/start`, `/volume`, `/pckapat` vb.) ve mesaj işleme. |
| **`utils/scheduler.py`** | APScheduler ile zil saatlerini planlar ve tetikler. |
| **`utils/event_emitter.py`** | Bileşenler arası (Bot <-> GUI <-> Media) haberleşmeyi sağlayan olay veriyolu. |

---

## 🛠️ Uygulanan Kritik Yamalar ve Çözümler

Proje geliştirme sürecinde karşılaşılan hatalar ve uygulanan kalıcı çözümler:

### 1. Ses Sistemi Çökmesi (Access Violation 0xC0000005)
*   **Sorun:** VLC `MediaPlayer` nesnelerinin sürekli oluşturulup silinmesi bellek hatasına yol açıyordu.
*   **Çözüm (`config/settings.py`):** `vlc.Instance` tek bir kez oluşturulup (`self.vlc_instance`) tüm uygulama boyunca saklandı. Player'lar bu ortak instance üzerinden türetildi.

### 2. Başlangıçta Kilitlenme ve "Meşguliyet" Hatası
*   **Sorun:** Windows açılışında ses kartı hazır olmadan ses çalmaya çalışılması sistemi "Meşgul" modunda kilitliyordu.
*   **Çözüm 1 (`gui/app.py`):** `_warmup_audio_system` fonksiyonu eklendi. Açılıştan 5 saniye sonra çalışarak ses motorunu yeniliyor ve sessiz bir `startup.wav` çalarak sistemi tetikliyor.
*   **Çözüm 2 (`config/settings.py`):** `play_media` fonksiyonuna "Yalancı Meşguliyet" koruması eklendi. Eğer sistem meşgul görünüyor ama ses çalmıyorsa, durum otomatik düzeltiliyor.

### 3. Kilit Dosyası (Lock File) Sorunu
*   **Sorun:** Elektrik kesintisi veya zorla kapanma sonrası `app.lock` silinmediği için uygulama "Zaten çalışıyor" diyerek açılmıyordu.
*   **Çözüm (`main.py`):** `cleanup_stale_locks` fonksiyonu geliştirildi. Bilgisayarın açılış saati (`boot_time`) kontrol edilerek, eski oturumdan kalan kilit dosyaları başlangıçta otomatik siliniyor.

### 4. Arayüz Donması (TTS İşlemleri)
*   **Sorun:** Ağır TTS modelleri yüklenirken arayüz donuyordu.
*   **Çözüm (`utils/tts_manager.py`):** Model yükleme işlemi `_delayed_startup` ile ayrı bir thread'e alındı ve açılıştan 15 saniye sonraya ertelendi.

### 5. Telegram ve GUI Senkronizasyonu
*   **Sorun:** Telegram'dan zil çalınca GUI'deki butonlar aktif kalıyordu (veya tam tersi).
*   **Çözüm:** `EventEmitter` yapısı güçlendirildi. `media_status_changed`, `stop_all_media` gibi olaylarla her iki tarafın durumu anlık eşitleniyor.

---

## ⚙️ Teknik Özellikler

*   **Dil:** Python 3.10+
*   **GUI:** Tkinter (Standart kütüphane)
*   **Ses Motoru:** `python-vlc` (VLC Media Player DLL'leri gerektirir)
*   **TTS Motoru:** `piper-tts` (ONNX tabanlı, çevrimdışı, Türkçe Fahrettin modeli)
*   **Veritabanı:** SQLite (`data/zil_db.sqlite`)
*   **Zamanlayıcı:** `APScheduler` (BackgroundScheduler)
*   **Bot Kütüphanesi:** `python-telegram-bot` (Async)
*   **Exe Derleme:** `PyInstaller` (Tek klasör modu)

---

## 📝 Geliştirici Notları

1.  **Derleme (Build):**
    Değişiklik yapıldığında `dist` klasörü silinmeli ve şu komut çalıştırılmalıdır:
    ```bash
    pyinstaller --clean --noconfirm HayriBot.spec
    ```

2.  **Ses Dosyaları:**
    `media/` klasöründeki dosya isimleri (`zil.mp3`, `tam.mp3` vb.) kod içinde sabittir (`config/settings.py`). Dosya değiştirilirken isimler korunmalıdır.

3.  **Git Yönetimi:**
    Hassas veriler (`zil_db.sqlite`, `app.log`) `.gitignore` ile hariç tutulmuştur.

---

*Bu belge, HayriBot V2.5 sürümü için oluşturulmuştur.*
```
