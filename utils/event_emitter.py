from pymitter import EventEmitter
from threading import Lock
import asyncio
from telegram.ext import Application
import logging
from queue import Queue, Empty  # ← Empty'i import et
import threading

logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('vlc').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('torch').setLevel(logging.WARNING)
logging.getLogger('TTS').setLevel(logging.INFO)

# Log ayarları (UTF-8 kodlamasını zorunlu kıl)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # Logger name eklendi
    level=logging.INFO,  # DEBUG yerine INFO
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

class ThreadSafeAsyncEventEmitter(EventEmitter):
    def __init__(self):
        super(ThreadSafeAsyncEventEmitter, self).__init__()
        self.bot_instance = None
        self._lock = Lock()
        self._async_lock = asyncio.Lock()
        self._debounce_timers = {}
        self._queue = Queue()  # ← YENİ: Event queue
        self._main_thread = threading.current_thread()
        self._shutdown_requested = False  # ← YENİ: Shutdown flag'i
        self._setup_media_events()
        
        # Queue işleyici thread
        def process_queue():
            while not self._shutdown_requested:
                try:
                    event_data = self._queue.get(timeout=1)
                    if event_data is None:  # Shutdown sinyali
                        break
                    event, args, kwargs = event_data
                    self._emit_direct(event, *args, **kwargs)
                    self._queue.task_done()  # ← YENİ: Task completed
                except Empty:
                    # Timeout normal, devam et
                    continue
                except Exception as e:
                    logging.error(f"Queue işleme hatası: {str(e)}", exc_info=True)
            logging.info("Event queue işleyici sonlandırıldı")
        
        self._queue_thread = threading.Thread(target=process_queue, daemon=True, name="EventQueueProcessor")
        self._queue_thread.start()

    def emit(self, event, *args, **kwargs):
        """Olayları thread-safe ve debouncing ile yay"""
        debounce_time = 0 if event == "zil_eklendi" else 0.2
        try:
            if threading.current_thread() is self._main_thread and asyncio.get_event_loop().is_running():
                # Ana thread'de ve loop çalışıyorsa direkt emit
                with self._lock:
                    if event in self._debounce_timers:
                        self._debounce_timers[event].cancel()
                    self._debounce_timers[event] = asyncio.get_event_loop().call_later(
                        debounce_time,
                        lambda: self._emit_direct(event, *args, **kwargs)
                    )
                    logging.debug(f"Olay yayımı planlandı: {event}, debounce={debounce_time}s")
            else:
                # Diğer thread'lerden queue'ya post et
                self._queue.put((event, args, kwargs))
                logging.debug(f"Olay kuyruğa eklendi: {event}")
        except Exception as e:
            logging.error(f"Olay yayımı hatası (emit): {event}, {str(e)}", exc_info=True)

    async def async_emit(self, event, *args, **kwargs):
        """Olayları asenkron ve thread-safe şekilde yay"""
        async with self._async_lock:
            try:
                if event in self._debounce_timers:
                    self._debounce_timers[event].cancel()
                self._debounce_timers[event] = asyncio.get_event_loop().call_later(
                    0.2,
                    lambda: self._emit_direct(event, *args, **kwargs)
                )
                logging.debug(f"Asenkron olay yayımı planlandı: {event}")
            except Exception as e:
                logging.error(f"Olay yayımı hatası (async_emit): {event}, {str(e)}", exc_info=True)

    def _emit_direct(self, event, *args, **kwargs):
        """Olayları gerçekten yayan yardımcı metod"""
        try:
            super(ThreadSafeAsyncEventEmitter, self).emit(event, *args, **kwargs)
            logging.debug(f"Olay yayınlandı: {event}")  # ← INFO yerine DEBUG
        except Exception as e:
            logging.error(f"Olay yayınlama hatası: {event}, {str(e)}", exc_info=True)

    def shutdown(self):
        """Queue'yu ve thread'i temizle"""
        try:
            self._shutdown_requested = True  # ← YENİ: Flag ile shutdown
            self._queue.put(None)  # Shutdown sinyali
            self._queue_thread.join(timeout=2)
            logging.info("EventEmitter queue kapatıldı")
        except Exception as e:
            logging.error(f"EventEmitter kapatma hatası: {str(e)}")

    def _setup_media_events(self):
        """Medya event'lerini kur"""
        @self.on("telegram_media_request")
        async def handle_telegram_media_request(data):
            """Telegram'dan gelen medya isteklerini GUI'ye yönlendir"""
            media_type = data.get('media_type')
            chat_id = data.get('chat_id')
            user_info = data.get('user_info', 'Telegram Kullanıcısı')
            
            logging.info(f"📱 Telegram medya isteği: {media_type} from {user_info}")
            
            # GUI'ye event gönder
            self.emit("gui_media_play", {
                'media_type': media_type,
                'source': 'telegram',
                'user_info': user_info,
                'chat_id': chat_id
            })
        
        @self.on("gui_media_play")
        def handle_gui_media_play(data):
            """GUI'de medya çalma event'i"""
            media_type = data.get('media_type')
            source = data.get('source', 'gui')
            user_info = data.get('user_info', '')
            
            logging.info(f"🎵 GUI medya çalma: {media_type} from {source}")
            
            # MediaManager üzerinden çal
            try:
                from config.settings import media_manager
                success = media_manager.play_media(media_type)
                
                if success:
                    logging.info(f"✅ Medya başarıyla çalındı: {media_type}")
                    
                    # Telegram'a bildirim gönder
                    if source == 'telegram':
                        self.emit("telegram_notification", {
                            'chat_id': data.get('chat_id'),
                            'message': f"✅ {media_type} çalınıyor...",
                            'user_info': user_info
                        })
                else:
                    logging.error(f"❌ Medya çalınamadı: {media_type}")
                    
            except Exception as e:
                logging.error(f"Medya çalma hatası: {str(e)}")
        

        @self.on("telegram_media_started")
        def handle_telegram_media_started(data):
            """Telegram'dan medya başladığında"""
            logging.info(f"📱 Telegram medya başladı: {data}")
        
        @self.on("stop_all_media")  
        def handle_stop_all_media(data):
            """Tüm medyaları durdur"""
            try:
                from config.settings import media_manager
                media_manager.stop_all_media()
                logging.info("🔴 Tüm medyalar durduruldu (event)")
            except Exception as e:
                logging.error(f"Durdurma hatası: {str(e)}")
                
        

ee = ThreadSafeAsyncEventEmitter()