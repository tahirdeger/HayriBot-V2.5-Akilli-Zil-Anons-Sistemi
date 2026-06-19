import asyncio
import aiohttp
import logging
from utils.event_emitter import ee

async def check_internet():
    # Google connectivity check - Güvenilir ve SSL sertifika hatası üretmeyen hızlı kontrol
    url = "http://clients3.google.com/generate_204" 
    try:
        # Timeout süresini artırdık (CPU yükü altında hata vermemesi için)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                return response.status in (200, 204)
    except:
        return False

async def check_internet_background():
    """
    Sadece internet durumunu kontrol eder ve değişiklikleri bildirir.
    Bot başlatma/durdurma işlemini yapmaz! Telegram kütüphanesi (PTB)
    zaten kendi içinde kopma durumunda tekrar bağlanmayı dener.
    """
    last_status = None 
    
    # İlk açılışta durumu tespit et
    last_status = await check_internet()
    logging.info(f"İnternet izleme servisi aktif. Durum: {'Online' if last_status else 'Offline'}")
    ee.emit("internet_status_changed", last_status)
    
    while True:
        try:
            # 10 saniye bekle
            await asyncio.sleep(10)
            
            current_status = await check_internet()
            
            # Eğer durum değiştiyse sadece bilgi ver
            if current_status != last_status:
                
                status_text = "🌐 Bağlantı sağlandı" if current_status else "❌ İnternet bağlantısı koptu"
                logging.info(status_text)
                
                # GUI ikonları için sinyal gönder (Sadece görsel güncelleme)
                ee.emit("internet_status_changed", current_status)
                
                # ÖNEMLİ DEĞİŞİKLİK:
                # restart_bot sinyalini KALDIRDIK. 
                # Telegram botu (Application) bağlantı koparsa kendisi retry yapar.
                # Bizim dışarıdan müdahale etmemiz Conflict yaratıyor.
                
                last_status = current_status
            
        except Exception as e:
            logging.error(f"İnternet döngüsü hatası: {e}")