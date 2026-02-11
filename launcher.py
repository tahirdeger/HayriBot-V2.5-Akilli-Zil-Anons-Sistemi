# ============================================
# HAYRİBOT V2.0 - WATCHDOG LAUNCHER
# Özellikler: İlk Kurulum Bildirimi, Hata Takibi, Aylık Rapor
# ============================================

import subprocess
import sys
import os
import time
import logging
import datetime
import socket
from pathlib import Path

# ============================================
# UYARILARI BASTIR
# ============================================
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")

import os
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning,ignore::UserWarning'

# ============================================
# ENCODING AYARLARI
# ============================================
if sys.platform == 'win32':
    import io
    import ctypes
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception as e:
        print(f"Encoding ayarı hatası: {e}")

# ============================================
# LOG AYARLARI
# ============================================
log_file = 'launcher.log'
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

log_path = os.path.join(base_dir, log_file)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# ============================================
# WATCHDOG LAUNCHER CLASS
# ============================================
class WatchdogLauncher:
    def __init__(self):
        """Watchdog Launcher'ı başlat"""
        try:
            # 1. Okul Adını Al
            try:
                # Veritabanı yolunu bul (EXE veya Py)
                if getattr(sys, 'frozen', False):
                    import sqlite3
                    db_path = os.path.join(base_dir, 'data', 'zil_db.sqlite')
                    # Launcher bir alt klasördeyse parent'a bak
                    if not os.path.exists(db_path):
                         db_path = os.path.join(os.path.dirname(base_dir), 'data', 'zil_db.sqlite')
                    
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT deger FROM ayarlar WHERE anahtar='school_name'")
                    res = cursor.fetchone()
                    self.school_name = res[0] if res and res[0] else "Tanımsız Okul"
                    conn.close()
                else:
                    # Geliştirme ortamı
                    from utils.database import init_db, ayar_getir
                    init_db()
                    self.school_name = ayar_getir("school_name") or "Tanımsız Okul"
            except:
                self.school_name = "HayriBot Sistemi"

            # 2. Ana Uygulama Yolunu Belirle
            if getattr(sys, 'frozen', False):
                # Launcher klasöründeyse, parent dizine git
                if "HayriBot_Launcher" in base_dir:
                    parent_dir = os.path.dirname(base_dir)
                    self.main_app = os.path.join(parent_dir, "HayriBot", "HayriBot.exe")
                else:
                    self.main_app = os.path.join(base_dir, "HayriBot.exe")
                
                # Yedek kontrol
                if not os.path.exists(self.main_app):
                     self.main_app = os.path.join(base_dir, "HayriBot", "HayriBot.exe")

                logging.info(f"EXE modu: Ana uygulama yolu: {self.main_app}")
            else:
                self.main_app = os.path.join(base_dir, "main.py")
                logging.info(f"Geliştirme modu: Ana uygulama yolu: {self.main_app}")

            # 3. Telegram Ayarları
            self.telegram_bot_token = "YÖNETİCİDEN ALINAN BOT TOKEN"
            self.chat_id = "YÖNETİCİDEN ALINAN CHAT ID"

        except Exception as e:
            logging.error(f"Launcher init hatası: {str(e)}")
            self.main_app = "HayriBot.exe"
            self.school_name = "Bilinmeyen Okul"
            self.telegram_bot_token = ""
            self.chat_id = ""

    def send_telegram_message(self, text):
        """Telegram mesajı gönder"""
        if not self.telegram_bot_token or not self.chat_id:
            return

        try:
            import requests
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            logging.error(f"Telegram gönderme hatası: {str(e)}")

    def check_first_install(self):
        """Uygulama bilgisayara ilk kez mi yükleniyor kontrol et"""
        try:
            install_lock_file = os.path.join(base_dir, '.install_info')
            
            # Eğer dosya yoksa -> İLK KURULUM
            if not os.path.exists(install_lock_file):
                pc_name = socket.gethostname()
                install_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                msg = f"🎉 **YENİ KURULUM BİLDİRİMİ**\n\n"
                msg += f"📍 **Okul:** {self.school_name}\n"
                msg += f"💻 **PC Adı:** {pc_name}\n"
                msg += f"🕒 **Tarih:** {install_date}\n"
                msg += f"✅ HayriBot V2.5 başarıyla yüklendi ve başlatıldı."
                
                self.send_telegram_message(msg)
                logging.info("İlk kurulum bildirimi gönderildi.")
                
                # Dosyayı oluştur ki bir daha göndermesin
                with open(install_lock_file, 'w') as f:
                    f.write(f"Installed: {install_date}\nPC: {pc_name}")
            
        except Exception as e:
            logging.error(f"İlk kurulum kontrolü hatası: {e}")

    def check_monthly_report(self):
        """Her ayın 1. günü rapor gönder"""
        try:
            today = datetime.date.today()
            
            # Sadece ayın 1. günü çalışır
            if today.day != 1:
                return

            # Rapor kontrol dosyası (tekrarlı gönderimi engellemek için)
            report_file = os.path.join(base_dir, '.last_report')
            
            # Eğer dosya varsa ve içindeki tarih bugünse gönderme
            if os.path.exists(report_file):
                with open(report_file, 'r') as f:
                    last_date = f.read().strip()
                if last_date == str(today):
                    return

            # Raporu gönder
            msg = f"📅 **Aylık Durum Raporu**\n\n"
            msg += f"📍 **Okul:** {self.school_name}\n"
            msg += f"🤖 **Uygulama:** HayriBot V2.5\n"
            msg += f"✅ Sistem bu ay sorunsuz çalıştı.\n"
            msg += f"🕒 Tarih: {today.strftime('%d.%m.%Y')}"
            
            self.send_telegram_message(msg)
            logging.info("📅 Aylık rapor gönderildi.")

            # Tarihi kaydet
            with open(report_file, 'w') as f:
                f.write(str(today))

        except Exception as e:
            logging.error(f"Aylık rapor hatası: {e}")

    def start_main_application(self):
        """Ana uygulamayı başlatır"""
        try:
            if not os.path.exists(self.main_app):
                return False, f"Dosya bulunamadı: {self.main_app}"

            working_dir = os.path.dirname(self.main_app)
            
            # Komut
            cmd = [self.main_app] if self.main_app.endswith('.exe') else [sys.executable, self.main_app]

            logging.info(f"🚀 Başlatılıyor: {self.main_app}")

            # DLL Çakışma Önlemi
            import ctypes
            try: ctypes.windll.kernel32.SetDllDirectoryW(None)
            except: pass

            # Uygulamayı başlat
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                return True, None
            else:
                error_out = (result.stderr or "") + (result.stdout or "")
                return False, error_out

        except Exception as e:
            return False, str(e)

    def monitor_application(self):
        """Ana döngü"""
        logging.info("🔍 Watchdog başlatıldı.")
        
        # 1. İlk Kurulum Kontrolü (Sadece ilk seferde çalışır)
        self.check_first_install()

        # 2. Aylık Rapor Kontrolü
        self.check_monthly_report()

        # 3. Ana Uygulamayı Başlat ve İZLE
        # Bu fonksiyon uygulama kapanana kadar bloklar (bekler)
        success, error_msg = self.start_main_application()

        if success:
            # BAŞARILI DURUM:
            # Eğer uygulama 'kapat' butonuyla düzgün kapatıldıysa
            # Watchdog da sessizce kapanır.
            logging.info("✅ Uygulama başarıyla çalıştı ve kapandı.")
            sys.exit(0)
        
        else:
            # HATA DURUMU:
            # Uygulama çöktüyse veya hata ile kapandıysa bildirim at
            logging.error(f"❌ Uygulama hatası: {error_msg}")
            
            # Log dosyasını oku (Son 20 satır)
            log_content = "Log dosyası okunamadı."
            try:
                app_log = os.path.join(os.path.dirname(self.main_app), 'app.log')
                if os.path.exists(app_log):
                    with open(app_log, 'r', encoding='utf-8', errors='replace') as f:
                        log_content = "".join(f.readlines()[-20:])
            except: pass

            # Telegram'a bildir
            msg = f"❌ **HATA BİLDİRİMİ**\n\n"
            msg += f"📍 **Okul:** {self.school_name}\n"
            msg += f"⚠️ **Durum:** HayriBot Hata Verdi/Çöktü\n"
            msg += f"🕒 **Zaman:** {time.strftime('%H:%M:%S')}\n\n"
            msg += f"**Hata Mesajı:**\n`{error_msg[:200]}`\n\n"
            msg += f"**Son Loglar:**\n`{log_content[:500]}`"
            
            self.send_telegram_message(msg)
            
            # Kullanıcıya GUI hatası göster
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("HayriBot Hatası", f"Uygulama beklenmedik şekilde kapandı!\n\nHata:\n{error_msg[:500]}\n\nYöneticiye rapor gönderildi.")
            except: pass
            
            sys.exit(1)

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    try:
        launcher = WatchdogLauncher()
        launcher.monitor_application()
    except Exception as e:
        logging.critical(f"Watchdog çöktü: {e}")