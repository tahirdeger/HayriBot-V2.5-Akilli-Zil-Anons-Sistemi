# utils/scheduler.py - ORİJİNAL YAPI + KORUMA

import asyncio
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
from config.settings import DB_PATH, media_manager
import logging
from utils.event_emitter import ee
import pytz
from apscheduler.jobstores.base import JobLookupError
import time
from apscheduler.triggers.cron import CronTrigger

# Zaman dilimi
try:
    TIMEZONE = pytz.timezone('Europe/Istanbul')
except pytz.exceptions.UnknownTimeZoneError:
    import tzlocal
    TIMEZONE = tzlocal.get_localzone()
    logging.warning(f"Varsayılan zaman dilimi kullanılıyor: {TIMEZONE}")

# ============================================================
# AYARLAR (SADECE BURASI EKLENDİ)
# ============================================================
# misfire_grace_time=60: Bilgisayar 60 saniye donsa bile,
# kendine gelince zili atlamaz, hemen çalar.
job_defaults = {
    'misfire_grace_time': 60,
    'coalesce': False,
    'max_instances': 5
}

# BackgroundScheduler (Ayarlarla birlikte)
scheduler = BackgroundScheduler(timezone=TIMEZONE, job_defaults=job_defaults)
# ============================================================

def play_zil(tur='ogrenci'):
    """Zamanlanmış zili çaldır - GUI üzerinden tetikle"""
    try:
        logging.info(f"⏰ ZAMANLAYICI TETİKLENDİ (play_zil): {tur}")
        from utils.database import is_bells_enabled
        
        # Zillerin aktif olup olmadığını kontrol et
        enabled = is_bells_enabled()
        logging.info(f"🔔 Zil Durumu: {'Aktif' if enabled else 'Pasif'}")
        
        if not enabled:
            logging.info(f"🔕 {tur.capitalize()} zili pasif olduğu için çalınmadı.")
            return
        
        # GUI'ye sinyal gönder (Sanki butona basılmış gibi)
        command_map = {
            'ogrenci': 'ogrenci_zil',
            'ogretmen': 'ogretmen_zil',
            'teneffus': 'cikis_zil'
        }
        
        command = command_map.get(tur, 'ogrenci_zil')
        logging.info(f"🚀 GUI'ye komut gönderiliyor: {command}")
        ee.emit("scheduler_play_request", command)
            
    except Exception as e:
        logging.error(f"❌ Zil tetikleme hatası: {str(e)}", exc_info=True)


async def baslat_zamanlayici(application=None):
    logging.info("⏰ baslat_zamanlayici fonksiyonu çağrıldı")
    register_events()
    try:
        if not scheduler.running:
            scheduler.start()
            logging.info("✅ Zamanlayıcı başlatıldı (BackgroundScheduler)")
        else:
            logging.info("Zamanlayıcı zaten çalışıyor")
        
        # Zamanlayıcıyı veritabanından yeniden yükle
        refresh_scheduler() 
        
        logging.info(f"Zamanlayıcı zaman dilimi: {scheduler.timezone}")
        
        # Aktif işleri listele
        jobs = scheduler.get_jobs()
        logging.info(f"Aktif zamanlayıcı işleri: {[job.id for job in jobs]}")

    except Exception as e:
        logging.error(f"❌ Zamanlayıcı başlatma hatası: {str(e)}", exc_info=True)
        raise

def register_events():
    logging.info("register_events fonksiyonu çağrıldı")

    # Ana event loop'u global olarak sakla
    try:
        main_loop = asyncio.get_event_loop()
    except RuntimeError:
        main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(main_loop)
        logging.debug("Yeni asyncio event loop oluşturuldu")

    @ee.on("veri_degisti")
    def handle_veri_degisti():
        logging.info("📢 veri_degisti event'i alındı")
        try:
            refresh_scheduler()
        except Exception as e:
            logging.error(f"Event hatası: {str(e)}", exc_info=True)

    @ee.on("zil_eklendi")
    def handle_zil_eklendi(saat, tur, job_id):
        logging.debug(f"zil_eklendi eventi alındı: saat={saat}, tur={tur}, job_id={job_id}")
        try:
            hour, minute = map(int, saat.split(':'))
            scheduler.add_job(
                play_zil,
                'cron',
                hour=hour,
                minute=minute,
                id=job_id,
                kwargs={'tur': tur},
                replace_existing=True
            )
            logging.info(f"⏰ Yeni job eklendi: {saat} ({tur}) → ID: {job_id}")
        except Exception as e:
            logging.error(f"❌ Event job ekleme hatası ({job_id}): {str(e)}", exc_info=True)


# refresh_scheduler fonksiyonunu ekle (mevcut kodların altına)
def refresh_scheduler():
    try:
        logging.info("🔄 Zamanlayıcı yenileniyor...")
        
        # Sadece zil joblarını temizle (varsa temizlik görevi kalsın)
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id != 'gunluk_temizlik':
                job.remove()
        
        from utils.database import listele_zil
        ziller = listele_zil()
        
        for zil in ziller:
            zil_id, saat, tur, job_id = zil
            try:
                hour, minute = map(int, saat.split(':'))
                scheduler.add_job(
                    play_zil,
                    'cron',
                    hour=hour,
                    minute=minute,
                    id=job_id,
                    kwargs={'tur': tur},
                    replace_existing=True
                )
                logging.info(f"⏰ Job eklendi: {saat} - {tur} ({job_id})")
            except Exception as e:
                logging.error(f"❌ Job eklenemedi ({saat}, {tur}): {str(e)}")

        logging.info(f"✅ Zamanlayıcı güncellendi → {len(scheduler.get_jobs())} aktif job")
    except Exception as e:
        logging.error(f"❌ Zamanlayıcı yenileme hatası: {str(e)}")


def cleanup_old_messages():
    """24 saatten eski mesajları temizle"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                DELETE FROM messages 
                WHERE timestamp < datetime('now', '-1 day')
            """)
            logging.info(f"Eski mesajlar temizlendi: {cursor.rowcount} adet")
    except Exception as e:
        logging.error(f"Mesaj temizleme hatası: {str(e)}")

# scheduler'ı başlattığınız yere bu işi ekleyin
try:
    scheduler.add_job(
        cleanup_old_messages,
        'cron',
        hour=3,
        minute=0,
        id='gunluk_temizlik'
    )
except: pass