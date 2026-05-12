import os
import sys
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from utils.database import is_bells_enabled
from utils.event_emitter import ee
import subprocess
import psutil
import time
import logging
import ctypes
import asyncio
from telegram.ext import ContextTypes



async def cleanup_telegram_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE, delay: int = 60):
    """
    Belirtilen süre sonra sohbeti temizler ve ana menüyü gösterir
    """
    try:
        await asyncio.sleep(delay)
        
        # Son 10 mesajı silmeye çalış
        try:
            async with context.bot:
                messages = []
                async for message in context.bot.get_chat_history(chat_id, limit=10):
                    messages.append(message.message_id)
                
                # Grup halinde sil (Telegram API limiti)
                for i in range(0, len(messages), 5):
                    batch = messages[i:i+5]
                    await context.bot.delete_messages(chat_id, batch)
                    await asyncio.sleep(0.3)
                    
        except Exception as e:
            logging.debug(f"Mesaj silme hatası (normal olabilir): {str(e)}")
        
        # Ana menüyü göster
        menu_text = (
            "🔔 HayriBotV1.4\n"
            "🏫 Zil ve Duyuru Sistemi\n"
            "islematolyesi.odoo.com | 2025\n"
            "\n🔄 Otomatik temizlik yapıldı. Yeniden hizmetinizdeyiz!"
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            reply_markup=create_keyboard()
        )
        
        logging.info(f"✅ Sohbet temizlendi: {chat_id}")
        
    except Exception as e:
        logging.error(f"Sohbet temizleme hatası: {str(e)}")

def schedule_cleanup(chat_id: int, context: ContextTypes.DEFAULT_TYPE, delay: int = 60):
    """
    Temizliği planlar - önceki zamanlayıcıyı iptal eder
    """
    # Önceki zamanlayıcıyı iptal et
    if hasattr(context, '_cleanup_task') and context._cleanup_task:
        context._cleanup_task.cancel()
    
    # Yeni zamanlayıcı başlat
    context._cleanup_task = asyncio.create_task(
        cleanup_telegram_chat(chat_id, context, delay)
    )



def get_duration(file_path):
    """Medya dosyasının süresini saniye cinsinden döndürür (VLC ile)."""
    try:
        # MediaManager'ın mevcut VLC instance'ını yeniden kullan
        try:
            from config.settings import media_manager
            vlc_instance = media_manager.vlc_instance
        except Exception:
            import vlc
            vlc_instance = vlc.Instance('--no-video --quiet')

        media = vlc_instance.media_new(str(file_path))
        media.parse()
        duration_ms = media.get_duration()
        media.release()
        if duration_ms > 0:
            return duration_ms / 1000.0
        logging.warning(f"VLC süre alınamadı: {file_path}, varsayılan 30s")
        return 30.0
    except Exception as e:
        logging.warning(f"Süre hesaplama hatası {file_path}: {e}")
        return 30.0


def create_keyboard():
    """Okul türüne göre özelleştirilmiş, düzenli klavye oluştur"""
    from utils.database import get_school_type
    
    school_type = get_school_type()
    is_imam_hatip = school_type == "imam_hatip"
    
    keyboard = [
        # 1. SATIR: Zil butonları (yan yana)
        [
            InlineKeyboardButton("🔔 Öğrenci", callback_data="ogrenci_zil"),
            InlineKeyboardButton("👩🏫 Öğretmen", callback_data="ogretmen_zil"),
            InlineKeyboardButton("🚪 Çıkış", callback_data="cikis_zil")
        ],
        # 2. SATIR: Özel sesler
        [
            InlineKeyboardButton("🎵 İstiklal", callback_data="marscal"),
            InlineKeyboardButton("🕯️ Saygı", callback_data="saygical"),
            InlineKeyboardButton("🚨 Siren", callback_data="sirencal")
        ],
    ]
    
    # İmam Hatip okulu ise Ezan ve Sela butonlarını ekle
    if is_imam_hatip:
        keyboard.append([
            InlineKeyboardButton("🕌 Ezan", callback_data="ezanoku"),
            InlineKeyboardButton("🕌 Sela", callback_data="selaoku")
        ])
    
    # 3. SATIR: İşlevsel butonlar
    keyboard.extend([
        [
            InlineKeyboardButton("📢 Duyuru", callback_data="textgiris"),
            InlineKeyboardButton("🔊 Ses", callback_data="volume_menu")
        ],
        [
            InlineKeyboardButton("⏹️ Tümünü Durdur", callback_data="tumunu_durdur"),  # TÜM SESLERİ DURDUR
            InlineKeyboardButton("🔔 Zil Yönet", callback_data="zil_yonet")
        ],
        [
            InlineKeyboardButton("🖥️ Kapat", callback_data="pckapat"),
            InlineKeyboardButton("ℹ️ Durum", callback_data="bilgisayardurum")
        ]
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard(action):
    """Onaylama klavyesi oluşturur"""
    # Action mapping: GUI action -> callback data action
    action_mapping = {
        'zil': 'zil',
        'ogretmen_zil': 'ogretmen',  # DÜZELTME: ogretmen_zil -> ogretmen
        'teneffus_zil': 'teneffus',  # DÜZELTME: teneffus_zil -> teneffus
        'mars': 'mars',
        'saygi': 'saygi', 
        'siren': 'siren',
        'ezan': 'ezan',
        'sela': 'sela',
        'kapat': 'kapat'
    }
    
    # Callback data'daki action ismini al
    callback_action = action_mapping.get(action, action)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Evet", callback_data=f"evet_{callback_action}"),
            InlineKeyboardButton("❌ Hayır", callback_data=f"hayır_{callback_action}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# DÜZELTİLMİŞ KISIM
def zil_yonetim_keyboard():
    bells_status = "Kapat" if is_bells_enabled() else "Aç"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Toplu Ekle", callback_data="toplu_ekle"),
            InlineKeyboardButton("➕ Tek Ekle", callback_data="tek_ekle")
        ],
        [
            InlineKeyboardButton("📋 Zil Listesi", callback_data="zil_list"),
            InlineKeyboardButton(f"🔔 Zilleri {bells_status}", callback_data="toggle_bells")
        ],
        [
            InlineKeyboardButton("❌ İptal", callback_data="ana_menu"),
            InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
        ]
    ])

def generate_job_id(saat: str, tur: str) -> str:
    """Türe göre job ID üretir"""
    parts = saat.split(':')
    tur_prefix = {
        'ogrenci': 'oz',
        'ogretmen': 'tz',
        'teneffus': 'tzf'
    }.get(tur, 'zil')
    return f"{tur_prefix}{parts[0].zfill(2)}{parts[1].zfill(2)}"

def zil_tur_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎓 Öğrenci Zili", callback_data="zil_tur_sec_ogrenci"),
            InlineKeyboardButton("👩🏫 Öğretmen Zili", callback_data="zil_tur_sec_ogretmen")
        ],
        [
            InlineKeyboardButton("🏃 Teneffüs Zili", callback_data="zil_tur_sec_teneffus"),
            InlineKeyboardButton("🔙 Geri", callback_data="zil_yonet")
        ]
    ])

def zil_devam_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Başka Zil Ekle", callback_data="devam_et")],
        [InlineKeyboardButton("✅ Tamam", callback_data="tamam")]
    ])

def toplu_ekle_devam_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Başka Toplu Ekle", callback_data="toplu_ekle_devam")],
        [InlineKeyboardButton("✅ Tamam", callback_data="tamam")]
    ])


def create_volume_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔇 Sessiz", callback_data="vol_mute"),
         InlineKeyboardButton("🔉 50%", callback_data="vol_50"),
         InlineKeyboardButton("🔊 100%", callback_data="vol_100")],
        [InlineKeyboardButton("➖ Azalt", callback_data="vol_down"),
         InlineKeyboardButton("➕ Artır", callback_data="vol_up")],
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="ana_menu")]
    ])

def get_lock_path():
    """Lock dosyasının tam yolunu döndürür"""
    return os.path.join(os.getcwd(), "app.lock")

def shutdown_system():
    """Sistemi kapatırken lock dosyasını silmek için yeterli süre tanı"""
    # Windows için 3 saniye gecikmeli kapatma
    os.system("shutdown /s /t 3")
    
    # Linux için (root yetkisi gerektirir)
    # os.system("shutdown -h now")

restarting = False  # Global flag

def restart_application():
    """Uygulamayı güvenli şekilde yeniden başlatır"""
    try:
        logging.info("🔄 Uygulama yeniden başlatılıyor...")
        
        # Geçerli process bilgileri
        current_pid = os.getpid()
        if getattr(sys, 'frozen', False):
            executable = sys.executable
        else:
            executable = sys.executable
            args = sys.argv
        
        # MediaManager'ı temizle
        try:
            from config.settings import media_manager
            media_manager.stop_all_media()
            # MediaManager singleton instance'ını sıfırla
            from config.settings import MediaManager
            MediaManager._instance = None
        except Exception as e:
            logging.warning(f"MediaManager temizleme hatası: {e}")
        
        # VLC process'lerini temizle
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                if 'vlc' in proc.info['name'].lower() and proc.info['pid'] != current_pid:
                    proc.terminate()
        except Exception as e:
            logging.warning(f"VLC temizleme hatası: {e}")
        
        # Yeni process başlat
        if getattr(sys, 'frozen', False):
            # EXE modu
            subprocess.Popen([executable], cwd=os.path.dirname(executable))
        else:
            # Python modu
            subprocess.Popen([executable] + args)
        
        logging.info(f"✅ Yeni process başlatıldı, mevcut process kapatılıyor (PID: {current_pid})")
        
        # Mevcut process'i güvenli kapat
        os._exit(0)
        
    except Exception as e:
        logging.error(f"❌ Yeniden başlatma hatası: {e}")
        # Fallback: Basit yeniden başlatma
        try:
            python = sys.executable
            subprocess.Popen([python] + sys.argv)
            sys.exit()
        except Exception as fallback_error:
            logging.error(f"Fallback yeniden başlatma hatası: {fallback_error}")
            os._exit(1)


def validate_audio_file(file_path):
    """Ses dosyasının geçerli olup olmadığını kontrol et"""
    try:
        if not os.path.exists(file_path):
            return False, "Dosya bulunamadı"
            
        if os.path.getsize(file_path) == 0:
            return False, "Dosya boş"
            
        # Basit bir ses dosyası kontrolü
        try:
            import wave
            with wave.open(file_path, 'rb') as f:
                frames = f.getnframes()
                if frames == 0:
                    return False, "Ses çerçevesi yok"
        except:
            # Wave olmayan dosyalar için alternatif kontrol
            try:
                from mutagen import File
                audio = File(file_path)
                if audio is None or audio.info.length == 0:
                    return False, "Geçersiz ses dosyası"
            except:
                # Son çare: dosya uzantısı kontrolü
                if not file_path.lower().endswith(('.wav', '.mp3', '.ogg')):
                    return False, "Desteklenmeyen dosya formatı"
                    
        return True, "Geçerli ses dosyası"
    except Exception as e:
        return False, f"Kontrol hatası: {str(e)}"