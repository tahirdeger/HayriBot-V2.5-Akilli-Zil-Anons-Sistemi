# 🔔 HayriBot V2.5 - Akıllı Okul Zil ve Anons Sistemi

**HayriBot**, okullar için özel olarak geliştirilmiş, **Telegram üzerinden uzaktan yönetilebilen**, **Yapay Zeka (TTS)** destekli ve çökme korumalı (Watchdog) bir okul otomasyon sistemidir.

Klasik zil programlarının aksine; internet kopsa dahi zilleri çalmaya devam eder, olası bir hata durumunda kendini otomatik onarır ve yazdığınız metinleri doğal insan sesiyle (Fahrettin Modeli) okula anons eder.

![HayriBot Arayüz Önizleme](https://via.placeholder.com/800x400?text=Uygulama+Ekran+Goruntusu+Buraya)
*(Buraya uygulamanızın ekran görüntüsünü ekleyebilirsiniz)*

---

## 🚀 Öne Çıkan Özellikler

- **📱 Telegram Entegrasyonu:** Okulun neresinde olursanız olun zilleri çalın, durdurun, anons yapın veya PC'yi kapatın.
- **🗣️ Yapay Zeka Anons (TTS):** Yazdığınız herhangi bir metni anında doğal Türkçe insan sesiyle seslendirir.
- **🛡️ Watchdog (Bekçi) Mimarisi:** Sistem çökmez! Launcher uygulaması ana sistemi sürekli izler ve hata durumunda yeniden başlatıp size rapor verir.
- **📅 Akıllı Zamanlayıcı:** Öğrenci, Öğretmen ve Teneffüs zillerini saniyesi saniyesine planlar.
- **🚨 Acil Durum Modları:** Tek tuşla Sivil Savunma Sireni, İstiklal Marşı, Saygı Duruşu veya Ezan/Sela okuma.
- **🔋 Çakışma Önleyici (Conflict Guard):** Telegram bağlantısını sürekli optimize eder, bağlantı hatalarını kendi kendine çözer.

---

## ⚙️ Sistem Mimarisi (Nasıl Çalışır?)

Bu proje, güvenliği ve sürekliliği sağlamak için **iki katmanlı** bir yapıya sahiptir:

1.  **Launcher (Bekçi) - `launcher.py`:**
    * Sistemin giriş kapısıdır.
    * Ana uygulamayı (`main.py`) başlatır ve arka planda sürekli izler.
    * Eğer ana uygulama çökerse, yöneticiye Telegram üzerinden hata raporu gönderir ve sistemi otomatik olarak yeniden başlatır.
    * Bilgisayar açılışında otomatik olarak bu dosya devreye girer.

2.  **Ana Uygulama - `main.py`:**
    * Arayüzü (GUI), zil çaldırmayı, zamanlayıcıyı ve Telegram botunu yöneten asıl programdır.

> **⚠️ ÖNEMLİ:** Uygulamayı her zaman **Launcher** (`launcher.py` veya `HayriBot_Launcher.exe`) üzerinden başlatmalısınız. Doğrudan `main.py` çalıştırılırsa koruma sistemi devre dışı kalır.

---

## 🛠️ Kurulum ve Çalıştırma

### Seçenek A: Kaynak Koddan Çalıştırma (Geliştiriciler İçin)

1.  **Gereksinimler:** Python 3.10 veya üzeri sürüm yüklü olmalıdır.
2.  **Repoyu Klonlayın:**
    ```bash
    git clone https://github.com/tahirdeger/HayriBot-V2.5-Akilli-Zil-Anons-Sistemi.git
    cd HayriBot-V2.5-Akilli-Zil-Anons-Sistemi
    ```
3.  **Kütüphaneleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Uygulamayı Başlatın:**
    Terminalden sadece şu komutu verin:
    ```bash
    python launcher.py
    ```

### Seçenek B: EXE Olarak Kullanma (Son Kullanıcılar İçin)

Eğer `dist` klasörü içindeki hazır EXE dosyasını kullanacaksanız:
1.  Klasörü bilgisayarınıza indirin.
2.  **`HayriBot_Launcher.exe`** dosyasına çift tıklayın.
3.  Program açılacaktır.

---

## 🔑 İlk Ayarlar: Telegram Bot Kurulumu

Uygulama ilk açıldığında veritabanı otomatik oluşur ancak sistemi uzaktan yönetebilmek için Telegram Bot bilgilerinizi girmeniz gerekir.

### 1. Bot Token ve ID Nasıl Alınır?

* **API Token:**
    1.  Telegram'da **@BotFather** kullanıcısını bulun.
    2.  `/newbot` yazın ve botunuza bir isim verin.
    3.  Size verilen uzun **HTTP API Token**'ı kopyalayın.

* **Kullanıcı ID (Admin Yetkisi):**
    1.  Telegram'da **@userinfobot** kullanıcısını bulun ve başlatın.
    2.  Size verdiği **"Id"** numarasını kopyalayın.

### 2. Programa Kayıt

1.  HayriBot arayüzünde sol taraftaki **"⚙ Telegram Ayarları"** (veya Sistem Ayarları) butonuna tıklayın.
2.  **API Key** kutusuna kopyaladığınız Token'ı yapıştırın.
3.  **İzin Verilen Kullanıcı ID'leri** kutusuna kendi ID'nizi yapıştırın (Birden fazla yönetici varsa virgülle ayırabilirsiniz).
4.  **"Ayarları Kaydet"** butonuna basın.
5.  Program otomatik olarak yeniden başlayacak ve Telegram botunuz aktif hale gelecektir. Artık telefondan `/start` yazarak sistemi yönetebilirsiniz.

---

## 📖 Kullanım Kılavuzu

### Zil Ekleme
* **Arayüzden:** "Saat" ve "Tür" (Öğrenci/Öğretmen) seçip "Ekle" butonuna basın.
* **Telegramdan:** Botunuza `08:30-08:40-09:20` (Öğrenci-Öğretmen-Teneffüs) formatında mesaj atarak toplu ekleme yapabilirsiniz.

### Ses Dosyası Değiştirme
* `media` klasörü içerisindeki `.mp3` dosyalarını aynı isimle değiştirerek zil seslerini özelleştirebilirsiniz.

### PC Kapatma
* Telegram botuna `bilgisayarı kapat` veya `/pckapat` yazdığınızda sistem onay ister. Onaylarsanız bilgisayar güvenli bir şekilde kapatılır.

---

## 📦 EXE Oluşturma (Build)

Projeyi geliştirdikten sonra dağıtılabilir `.exe` formatına çevirmek için `PyInstaller` kullanılır.

1.  Tüm bağımlılıkların yüklü olduğundan emin olun.
2.  Terminalde şu komutu çalıştırın:
    ```bash
    pyinstaller HayriBot.spec --clean --noconfirm
    ```
3.  İşlem bittiğinde `dist/HayriBot_Final` klasörü içerisinde çalışmaya hazır dosyalar oluşacaktır.

---

## 📂 Proje Yapısı

```text
HayriBot/
├── launcher.py       # Bekçi uygulaması (Giriş noktası)
├── main.py           # Ana uygulama mantığı
├── HayriBot.spec     # PyInstaller yapılandırma dosyası
├── config/           # Ayar dosyaları
├── data/             # Veritabanı (Otomatik oluşur)
├── gui/              # Arayüz kodları (Tkinter)
├── handlers/         # Telegram komut işleyicileri
├── hooks/            # Derleme kancaları
├── media/            # Zil ve ses dosyaları
├── models/           # TTS Yapay zeka modelleri
└── utils/            # Yardımcı araçlar (Veritabanı, TTS, Scheduler vb.)


Bu proje açık kaynaklıdır ve eğitim kurumlarına fayda sağlamak amacıyla geliştirilmiştir. Katkıda bulunmak isterseniz:

Bu repoyu Fork'layın.

Yeni bir dal (branch) açın.

Değişikliklerinizi yapıp Pull Request gönderin.

Geliştirici: Tahir Değer
WEB: https://islematolyesi.odoo.com/blog/verimlilik-araclari-4/hayribot-v2-5-akilli-zil-ve-anons-sistemi-10