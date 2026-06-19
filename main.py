# ============================================
# HAYRİBOT V1.6 - ANA UYGULAMA 
# ============================================

import os
import sys
import io
import time
import asyncio
import logging
import threading
import multiprocessing
import psutil
import warnings
import atexit
from logging.handlers import RotatingFileHandler
from filelock import FileLock, Timeout
import tkinter as tk
from tkinter import messagebox

# Telegram
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import Conflict, NetworkError

# Proje Modülleri
from gui.preloader import PreloaderWindow
from utils.database import ayar_kaydet, init_db, ayar_getir, close_db_connections, DB_PATH, is_first_run
from utils.scheduler import baslat_zamanlayici
from gui.app import run_gui
from utils.internet_check import check_internet, check_internet_background
from utils.startup import add_to_startup, remove_from_startup
from utils.helpers import create_keyboard

# Uyarıları filtrele
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")

# ============================================
# ORTAM AYARLARI
# ============================================
def setup_environment():
    """Çalışma ortamını (EXE/Python) algıla ve yolları ayarla"""
    if getattr(sys, 'frozen', False):
        base_exe_dir = os.path.dirname(sys.executable)
        internal_dir = os.path.join(base_exe_dir, '_internal')
        
        # Olası Tcl/Tk yolları (Sırasıyla dene)
        possible_tcl_paths = [
            os.path.join(internal_dir, 'lib', 'tcl8.6'),
            os.path.join(internal_dir, 'tcl'),
            os.path.join(base_exe_dir, 'tcl'),
        ]
        
        possible_tk_paths = [
            os.path.join(internal_dir, 'lib', 'tk8.6'),
            os.path.join(internal_dir, 'tk'),
            os.path.join(base_exe_dir, 'tk'),
        ]

        # Geçerli yolu bul
        tcl_path = next((p for p in possible_tcl_paths if os.path.exists(os.path.join(p, 'init.tcl'))), None)
        tk_path = next((p for p in possible_tk_paths if os.path.exists(os.path.join(p, 'tk.tcl'))), None)

        if tcl_path and tk_path:
            os.environ['TCL_LIBRARY'] = tcl_path
            os.environ['TK_LIBRARY'] = tk_path
            # logging.info(f"Tcl/Tk yolları ayarlandı: {tcl_path}") # Log henüz aktif değil, print kullan
        
        # DLL Yolu
        if os.path.exists(internal_dir):
            os.environ['PATH'] = internal_dir + os.pathsep + os.environ.get('PATH', '')
            if hasattr(os, 'add_dll_directory'):
                try: os.add_dll_directory(internal_dir)
                except: pass

    # Unicode Desteği
    try:
        if sys.platform == 'win32':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
    except: pass

setup_environment()

# ============================================
# GLOBAL DEĞİŞKENLER
# ============================================
LOCK_FILE = "app.lock"
lock = FileLock(f"{LOCK_FILE}.lock", timeout=3)
current_bot_application = None
is_restarting = False  # Restart işlemi kilit mekanizması

# ============================================
# LOGLAMA
# ============================================
def setup_logging():
    log_file = "app.log"
    log_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
    log_path = os.path.join(log_dir, log_file)
    logging.getLogger().handlers = []
    file_handler = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
    for lib in ['httpcore', 'httpx', 'telegram', 'apscheduler', 'PIL', 'urllib3']:
        logging.getLogger(lib).setLevel(logging.WARNING)

# ============================================
# SİSTEM YÖNETİMİ
# ============================================
def check_and_kill_watchdog():
    try:
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name']):
            if 'launcher' in proc.info['name'].lower() and proc.info['pid'] != current_pid:
                proc.terminate()
    except: pass

def check_single_instance():
    try:
        lock.acquire()
        with open(LOCK_FILE, "w") as f: f.write(str(os.getpid()))
    except Timeout:
        try:
            with open(LOCK_FILE, "r") as f: pid = int(f.read().strip())
            if not psutil.pid_exists(pid):
                os.remove(LOCK_FILE)
                if os.path.exists(f"{LOCK_FILE}.lock"): os.remove(f"{LOCK_FILE}.lock")
                lock.acquire()
            else:
                logging.error("Uygulama zaten çalışıyor!")
                sys.exit(1)
        except: sys.exit(1)

def release_app_lock():
    try:
        for proc in psutil.process_iter(['name']):
            if 'vlc' in proc.info['name'].lower():
                try: proc.kill() 
                except: pass
        if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)
        if os.path.exists(f"{LOCK_FILE}.lock"): os.remove(f"{LOCK_FILE}.lock")
        close_db_connections()
    except: pass

def cleanup_stale_locks():
    """Başlangıçta bayat kilit dosyalarını temizle"""
    try:
        # Boot zamanını al (Sistem açılış zamanı)
        boot_time = psutil.boot_time()
        
        # 1. app.lock kontrolü
        if os.path.exists(LOCK_FILE):
            try:
                # Dosya değiştirilme zamanı boot'tan önceyse kesinlikle bayattır
                file_mtime = os.path.getmtime(LOCK_FILE)
                if file_mtime < boot_time:
                    logging.warning("⚠️ Kilit dosyası sistem açılışından eski, siliniyor...")
                    os.remove(LOCK_FILE)
                    if os.path.exists(f"{LOCK_FILE}.lock"):
                        try: os.remove(f"{LOCK_FILE}.lock")
                        except: pass
                else:
                    # Dosya yeni ise PID kontrolü yap
                    with open(LOCK_FILE, "r") as f:
                        content = f.read().strip()
                        if content:
                            pid = int(content)
                            if not psutil.pid_exists(pid):
                                logging.warning(f"⚠️ Bayat kilit dosyası bulundu (PID: {pid}), temizleniyor...")
                                os.remove(LOCK_FILE)
                                if os.path.exists(f"{LOCK_FILE}.lock"):
                                    try: os.remove(f"{LOCK_FILE}.lock")
                                    except: pass
            except Exception as e:
                logging.error(f"Lock dosyası okuma/silme hatası: {e}")
                try: os.remove(LOCK_FILE)
                except: pass

        # 2. FileLock'un bıraktığı .lock dosyası
        if os.path.exists(f"{LOCK_FILE}.lock"):
            try:
                lock_mtime = os.path.getmtime(f"{LOCK_FILE}.lock")
                if lock_mtime < boot_time:
                     os.remove(f"{LOCK_FILE}.lock")
                elif not os.path.exists(LOCK_FILE):
                     os.remove(f"{LOCK_FILE}.lock")
            except: pass
            
    except Exception as e:
        logging.error(f"Kilit temizleme genel hatası: {e}")

def safe_restart():
    release_app_lock()
    try: lock.release()
    except: pass

# ============================================
# TELEGRAM BOT İŞLEMLERİ
# ============================================
def set_current_bot_application(application):
    global current_bot_application
    current_bot_application = application

async def handle_restart_bot():
    """Botu güvenli bir şekilde yeniden başlatır (Conflict önlemeli)"""
    global current_bot_application, is_restarting
    
    if is_restarting:
        logging.warning("⚠️ Bot restart işlemi zaten sürüyor, yeni istek reddedildi.")
        return

    is_restarting = True
    logging.info("🔄 Bot yeniden başlatılıyor...")
    
    # 1. Eski botu tamamen durdur
    if current_bot_application:
        try:
            if current_bot_application.updater and current_bot_application.updater.running:
                await current_bot_application.updater.stop()
            if current_bot_application.running:
                await current_bot_application.stop()
            await current_bot_application.shutdown()
        except Exception as e:
            logging.error(f"Eski bot durdurulurken hata: {e}")
        finally:
            current_bot_application = None
    
    # 2. Telegram sunucularının oturumu kapatması için bekle
    await asyncio.sleep(3) 
    
    # 3. Yeni botu başlat
    await start_telegram_bot_async()
    
    is_restarting = False

def setup_handlers(app: Application):
    from handlers import command_handlers, callback_handlers
    app.add_handler(CommandHandler('start', command_handlers.start))
    app.add_handler(CommandHandler('volume', command_handlers.volume))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.handle_text))
    app.add_handler(CallbackQueryHandler(callback_handlers.button_handler))
    app.add_handler(CommandHandler("api_key", command_handlers.handle_api_key_change))
    app.add_handler(CommandHandler('togglebells', command_handlers.toggle_bells))

async def start_telegram_bot_async():
    """Bot başlatma (Ultra Güvenli Mod - DÜZELTİLMİŞ)"""
    global current_bot_application
    
    if current_bot_application and current_bot_application.running:
        logging.warning("⚠️ Bot zaten çalışıyor, başlatma isteği reddedildi.")
        return current_bot_application

    if not os.path.exists(DB_PATH): return None
    BOT_TOKEN = ayar_getir("telegram_api_key")
    if not BOT_TOKEN or "Api key" in BOT_TOKEN: return None

    # İnternet kontrolü (Sadece log için)
    if not await check_internet():
        logging.warning("İnternet bağlantısı yok, bot yine de başlatılacak (Retries için).")

    try:
        logging.info("Telegram botu başlatılıyor...")
        
        if current_bot_application:
            try:
                await current_bot_application.stop()
                await current_bot_application.shutdown()
            except: pass
            current_bot_application = None

        app = Application.builder().token(BOT_TOKEN).build()
        setup_handlers(app)
        await app.initialize()
        
        try:
            await app.bot.delete_webhook(drop_pending_updates=True)
        except: pass

        await app.start()
        
        # --- DÜZELTİLEN KISIM ---
        await app.updater.start_polling(
            drop_pending_updates=True, 
            allowed_updates=["message", "callback_query"],
            poll_interval=1.0,
            timeout=30, 
            bootstrap_retries=-1
        )
        # ------------------------
        
        set_current_bot_application(app)
        
        asyncio.create_task(send_startup_notification(app))
        
        logging.info("✅ Telegram botu başarıyla başlatıldı.")
        return app

    except Conflict:
        logging.critical("❌ CONFLICT HATASI: Başka bir bot örneği çalışıyor! (Otomatik düzeltme deneniyor...)")
        if current_bot_application:
            try:
                await current_bot_application.shutdown()
            except: pass
            current_bot_application = None
        return None
        
    except NetworkError:
        logging.error("❌ Ağ hatası: Bot başlatılamadı (İnternet yok mu?)")
        return None
        
    except Exception as e:
        logging.error(f"Bot başlatma hatası: {e}")
        return None

async def send_startup_notification(app):
    await asyncio.sleep(5)
    try:
        allowed_ids = ayar_getir("allowed_user_ids")
        if not allowed_ids: return
        msg = f"🔔 *HayriBot Başlatıldı*\n✅ Sistem Aktif\n🕒 {time.strftime('%H:%M:%S')}"
        for uid in allowed_ids.split(','):
            if uid.strip():
                try:
                    await app.bot.send_message(chat_id=uid.strip(), text=msg, parse_mode='Markdown', reply_markup=create_keyboard())
                except: pass
    except: pass

def start_async_tasks(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_internet_background())

# ============================================
# ANA AKIŞ
# ============================================
def main():
    try:
        if is_first_run():
            preloader = PreloaderWindow()
            st = preloader.run()
            ayar_kaydet("school_type", st)
    except: ayar_kaydet("school_type", "normal")

    try:
        if ayar_getir("startup_asked") != "1":
            root = tk.Tk()
            root.withdraw()
            if messagebox.askyesno("Başlangıç", "Windows açılışında otomatik başlasın mı?"):
                add_to_startup()
                ayar_kaydet("startup_enabled", "1")
            else:
                remove_from_startup()
                ayar_kaydet("startup_enabled", "0")
            ayar_kaydet("startup_asked", "1")
            root.destroy()
    except: pass

    setup_logging()
    cleanup_stale_locks()  # <--- Bayat kilitleri temizle
    check_single_instance()
    atexit.register(release_app_lock)
    atexit.register(safe_restart)
    init_db()
    
    loop = asyncio.new_event_loop()

    # Event dinleyicisi tanımla
    def on_restart_bot():
        logging.info("event emitter: restart_bot sinyali alındı, bot yeniden başlatılıyor...")
        asyncio.run_coroutine_threadsafe(handle_restart_bot(), loop)
    from utils.event_emitter import ee
    ee.on("restart_bot", on_restart_bot)

    async_thread = threading.Thread(target=start_async_tasks, args=(loop,), daemon=True)
    async_thread.start()

    # Zamanlayıcıyı Telegram'dan bağımsız başlat (token yoksa bile ziller çalsın)
    from utils.scheduler import baslat_zamanlayici
    asyncio.run_coroutine_threadsafe(baslat_zamanlayici(), loop)

    asyncio.run_coroutine_threadsafe(start_telegram_bot_async(), loop)

    try:
        logging.info("GUI Başlatılıyor...")
        check_and_kill_watchdog()
        run_gui(loop)
    except KeyboardInterrupt: pass
    except Exception as e:
        if not getattr(sys, 'frozen', False):
            logging.error(f"GUI Hatası: {e}")
            messagebox.showerror("Hata", f"Uygulama Hatası:\n{e}")
    finally:
        if current_bot_application:
            try:
                loop.run_until_complete(current_bot_application.stop())
                loop.run_until_complete(current_bot_application.shutdown())
            except: pass
        safe_restart()

    if getattr(sys, 'frozen', False):
        if not ayar_getir("telegram_api_key"):
            while True: time.sleep(60)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        multiprocessing.freeze_support()
    
    if getattr(sys, 'frozen', False):
        try:
            d = os.path.dirname(sys.executable)
            t = os.path.join(d, 'write_test')
            with open(t, 'w') as f: f.write('ok')
            os.remove(t)
        except:
            messagebox.showwarning("İzin Hatası", "Lütfen uygulamayı 'data' klasörüne yazma izni olan bir yere taşıyın.")

    main()