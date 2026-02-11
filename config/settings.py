#*config/settings.py*
import asyncio
import sys
import threading
import time
import vlc
from pathlib import Path
from utils.path_resolver import get_media_path, get_data_path
import logging
import wave
from utils.event_emitter import ee
import os
from tkinter import messagebox
from utils.path_resolver import get_data_path
from utils.helpers import get_duration
from utils.path_resolver import get_data_path, get_model_path

DB_PATH = get_data_path("zil_db.sqlite")

class MediaManager:
    _instance = None
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # Başlatma durumunu takip et
        return cls._instance
    
    def __init__(self):
        if not getattr(self, '_initialized', False):  # Yalnızca bir kez başlat
            import asyncio
            self.loop = asyncio.get_event_loop()  # Ana olay döngüsünü sakla
            self.players = {}
            self.is_playing = False
            self.currently_playing = None
            self.is_busy = False  # Yeni ekle: meşguliyet durumu
            self.busy_message = ""  # Yeni ekle: meşguliyet mesajı
            self._cancellation_flag = False
            self._init_manager()
            self._initialized = True
    
    def _init_manager(self):
        # EXE modunda ise, EXE'nin yanındaki 'media' klasörüne bak
        if getattr(sys, 'frozen', False):
            exe_path = Path(sys.executable).parent
            local_media = exe_path / "media"
            if local_media.exists():
                self.MEDIA_DIR = local_media
            else:
                self.MEDIA_DIR = get_media_path()
        else:
            self.MEDIA_DIR = get_media_path()
    
        logging.info(f"MEDIA DİZİNİ KONTROL: {self.MEDIA_DIR}")  # Eski log kalır
        
        if not self.MEDIA_DIR.exists():  # Eski kod kalır, ama Path.exists() ile uyumlu
            logging.critical(f"MEDIA DİZİNİ YOK: {self.MEDIA_DIR}")
            try:
                os.makedirs(self.MEDIA_DIR, exist_ok=True)  # Eski kod kalır
                logging.info(f"Media dizini oluşturuldu: {self.MEDIA_DIR}")
            except Exception as e:
                logging.error(f"Media dizini oluşturma hatası: {str(e)}")
                messagebox.showerror(  # Eski kod kalır
                    "Hata",
                    f"Media dizini oluşturulamadı: {self.MEDIA_DIR}\n"
                    "Lütfen uygulama dizininde yazma izinlerini kontrol edin."
                )
                sys.exit(1)
    
        # VLC Instance'ı tek bir kez oluştur ve sakla (Access Violation önlemi)
        self.vlc_instance = vlc.Instance('--no-video --quiet')
        
        self.players = {}
        self.is_playing = False
        self.currently_playing = None
        self.global_volume = 0.8
        self._load_media_files()
        self._set_volumes()
        logging.info(f"✅ MediaManager initialized. Media path: {self.MEDIA_DIR}")
    

    def cancel_all_operations(self):
        """Tüm medya operasyonlarını iptal et - GÜNCELLENDİ"""
        try:
            self._cancellation_flag = True
            self.stop_all_media()
            logging.info("🔴 Tüm medya operasyonları iptal edildi")
            
            # Meşguliyeti hemen kaldır ve butonları aktif yap
            self.set_busy_status(False, "")
            
            # Flag'i hemen sıfırla
            self._cancellation_flag = False
            logging.debug("İptal flag'i sıfırlandı")
            
        except Exception as e:
            logging.error(f"İptal işlemi hatası: {str(e)}")
        
    def is_cancelled(self):
        """İptal durumunu kontrol et"""
        return getattr(self, '_cancellation_flag', False)
    
    def reset_cancellation(self):
        """İptal flag'ini sıfırla"""
        self._cancellation_flag = False
        logging.debug("İptal flag'i manuel olarak sıfırlandı")


    def _load_media_files(self):
        media_files = {
            'zil': "zil.mp3",
            'ogretmen_zil': "ogretmen_zil.mp3",
            'teneffus_zil': "teneffus_zil.mp3",
            'anons': "anons.mp3",  # Ekstra eminlik için ekledim
            'tgmesaj': "tgmesaj.mp3",
            'mars': "istiklal.mp3",
            'saygi': "saygi.mp3",
            'siren': "siren.mp3",
            'tekrar': "tekrar.wav",
            'ezan': "ezan.mp3",
            'sela': "sela.mp3",
            'startup': "startup.wav"
        }
        
        for name, file in media_files.items():
            file_path = self.MEDIA_DIR / file
            
            # Startup dosyası yoksa sessiz wav oluştur
            if name == 'startup' and not file_path.exists():
                try:
                    with wave.open(str(file_path), 'w') as f:
                        f.setnchannels(1)
                        f.setsampwidth(2)
                        f.setframerate(44100)
                        f.writeframes(b'\x00' * 22050) # 0.5 sn sessizlik
                    logging.info(f"Startup sesi oluşturuldu: {file_path}")
                except Exception as e:
                    logging.error(f"Startup sesi oluşturma hatası: {e}")

            if not file_path.exists():
                logging.error(f"Medya dosyası bulunamadı: {file_path}")
                try:
                    with open(file_path, 'wb') as f:
                        f.write(b'')  # Boş dosya oluştur
                    logging.warning(f"⚠️ Boş dosya oluşturuldu: {file_path}")
                except Exception as e:
                    logging.error(f"❌ Dosya oluşturma hatası: {str(e)}")
                continue
                
            try:
                # Shared instance kullanarak player oluştur
                media = self.vlc_instance.media_new(str(file_path))
                player = self.vlc_instance.media_player_new()
                player.set_media(media)
                self.players[name] = {'path': str(file_path), 'player': player}
                logging.debug(f"Medya yüklendi: {name} -> {file_path}")
            except Exception as e:
                logging.error(f"Medya yükleme hatası ({name}): {str(e)}")
        
        
    def _check_player_state(self, player, name):
        """Oynatıcının durumunu kontrol eder ve gerekirse bayrakları sıfırlar"""
        try:
            # Player'ın hala geçerli olup olmadığını kontrol et
            if player is None:
                self.is_playing = False
                self.currently_playing = None
                self.set_busy_status(False, "")  # Hata durumunda meşguliyeti kaldır
                return
                
            if not player.is_playing() and self.is_playing and self.currently_playing == name:
                self.is_playing = False
                self.currently_playing = None
                self.set_busy_status(False, "")  # Bitiş durumunda meşguliyeti kaldır
                try:
                    self.loop.call_soon_threadsafe(
                        lambda: ee.emit("media_ended", "state_check")
                    )
                except Exception as e:
                    logging.error(f"Olay yayınlama hatası: {str(e)}")
        except Exception as e:
            # "access violation" hatalarını yakala ve görmezden gel
            if "access violation" in str(e).lower():
                logging.debug(f"Player erişim hatası ({name}), normal durum")
            else:
                logging.error(f"Oynatıcı durumu kontrol hatası ({name}): {str(e)}")
    
    def _set_volumes(self):
        for name, player in self.players.items():
            try:
                player.audio_set_volume(int(self.global_volume * 100))
                logging.debug(f"Başlangıç ses seviyesi ayarlandı: {name}, {self.global_volume*100}%")
            except Exception as e:
                logging.error(f"Ses seviyesi ayarlama hatası ({name}): {str(e)}")
    
    def is_media_busy(self):
        """Medya oynatıcının gerçekten meşgul olup olmadığını kontrol eder"""
        # ⚠️ Sadece gerçekten çalıyorsa meşgul say
        return self.is_busy and self.is_playing

    def get_busy_message(self):
        """Mevcut meşguliyet mesajını döndürür"""
        return self.busy_message

    def set_busy_status(self, is_busy, message=""):
        """Meşguliyet durumunu ayarlar ve event yayar"""
        self.is_busy = is_busy
        self.busy_message = message
        
        # GUI'yi güncellemek için event yay
        try:
            self.loop.call_soon_threadsafe(
                lambda: ee.emit("media_busy_status", {
                    "is_busy": is_busy,
                    "message": message
                })
            )
        except Exception as e:
            logging.error(f"Media busy status event hatası: {str(e)}")
        
        logging.info(f"Meşguliyet durumu: {is_busy}, Mesaj: {message}")

    def _on_media_ended(self, event):
        """Medya çalma tamamlandığında veya durdurulduğunda çağrılır - DÜZELTİLMİŞ"""
        try:
            logging.info(f"⏹ Medya olayı: {event.type}, Şu anda çalıyor: {self.currently_playing}")
            
            # Durumları sıfırla
            self.is_playing = False
            self.currently_playing = None
            self.set_busy_status(False, "")  # Meşguliyeti kaldır
            
            # Event yay
            self.loop.call_soon_threadsafe(
                lambda: ee.emit("media_ended", str(event.type))
            )
            
            logging.info("✅ Medya durumu sıfırlandı")
            
        except Exception as e:
            logging.error(f"Medya olayı yayınlama hatası: {str(e)}", exc_info=True)
            # Hata durumunda da durumları sıfırlamaya çalış
            self.is_playing = False
            self.currently_playing = None
            self.is_busy = False
            self.busy_message = ""


    def play_media(self, name, source='gui'):
        """
        Medya çal - TELEGRAM-GUI SENKRONİZASYONLU GÜNCELLEME
        """
        try:
            # ⚠️ KORUMA: Kilitli kalmış meşguliyet durumunu düzelt
            if self.is_busy and not self.is_playing:
                logging.warning("⚠️ Tespit edilen kilitli meşguliyet durumu düzeltiliyor...")
                self.set_busy_status(False, "")

            # Önce meşguliyet kontrolü - TELEGRAM İÇİN FARKLI DAVRAN
            if self.is_busy and source == 'telegram':
                # Telegram istekleri için daha esnek kontrol
                if self.is_playing:  # Sadece gerçekten çalıyorsa engelle
                    error_msg = f"⚠️ Şu anda {self.busy_message} çalıyor. Lütfen bekleyin..."
                    logging.warning(error_msg)
                    
                    # Telegram'a hata mesajı gönder
                    ee.emit("telegram_notification", {
                        'message': error_msg,
                        'alert': True
                    })
                    return False
            
            # Meşguliyet durumunu AYARLA - kaynağa göre farklı mesaj
            media_names = {
                'zil': 'Öğrenci Zili',
                'ogretmen_zil': 'Öğretmen Zili', 
                'teneffus_zil': 'Teneffüs Zili',
                'mars': 'İstiklal Marşı',
                'saygi': 'Saygı Duruşu',
                'siren': 'Acil Siren',
                'ezan': 'Ezan',
                'sela': 'Sela',
                'tts_temp': 'Metin Seslendirme',
                'startup': 'Sistem Başlatılıyor'
            }
            display_name = media_names.get(name, name)
            
            # TELEGRAM İSTEKLERİ İÇİN ÖZEL MESAJ
            if source == 'telegram':
                display_name = f"Telegram - {display_name}"
            
            # ⚠️ MEDYA ÇALMA İŞLEMİ - TELEGRAM İÇİN EVENT TETİKLE
            result = self._original_play_media(name)
            
            if result:
                # Meşguliyeti ayarla - kaynağı da belirt
                self.set_busy_status(True, display_name)
                
                # GUI'ye durum güncellemesi gönder - TELEGRAM İÇİN ÖZEL
                if source == 'telegram':
                    ee.emit("telegram_media_started", {
                        'media_type': name,
                        'display_name': display_name,
                        'source': source
                    })
                else:
                    ee.emit("media_status_changed", {
                        'playing': True,
                        'media_type': name,
                        'display_name': display_name,
                        'source': source
                    })
                    
                logging.info(f"▶️ {display_name} çalınıyor (kaynak: {source})")
            else:
                logging.warning(f"❌ Medya çalınamadı: {name}")
            
            return result
            
        except Exception as e:
            error_msg = f"Medya çalma hatası: {str(e)}"
            logging.error(error_msg)
            return False
    
    def _original_play_media(self, name):
        """ORİJINAL play_media metodunuzu buraya taşıyın - DEĞİŞTİRMEDEN"""
        # ⚠️ BURAYA MEVCUT play_media METODUNUZUN TAM İÇERİĞİNİ KOPYALAYIN
        # Aşağıdaki kodu silip sizin mevcut play_media kodunuzu yapıştırın
        
        if name == "stop_all":
            self.stop_all_media()
            return True

        if self.is_busy:
            error_msg = f"🎵 {name} çalınamadı, şu anda {self.busy_message} çalıyor"
            logging.warning(error_msg)
            ee.emit("play_error", error_msg)
            return False
            
        if name not in self.players:
            error_msg = f"🎵 {name} adlı medya bulunamadı"
            logging.error(error_msg)
            ee.emit("play_error", error_msg)
            return False
        
        if self.is_playing:
            logging.warning(f"🎵 {name} çalınamadı, şu anda {self.currently_playing} çalıyor")
            self.stop_all_media()
            time.sleep(0.5)
        
        try:
            # Düzeltme: file_path'i önceden al (release öncesi)
            player_data = self.players[name]
            file_path = player_data['path']
            
            # Eski player varsa temizle
            if player_data['player']:
                old_player = player_data['player']
                try:
                    old_player.stop()
                    old_player.release()  # Release et
                    logging.debug(f"Eski player release edildi: {name}")
                except Exception as e:
                    logging.warning(f"Eski player temizleme hatası ({name}): {str(e)}")
                player_data['player'] = None
            
            # Yeni player oluştur (her seferinde taze)
            # Shared instance kullanarak oluştur
            media = self.vlc_instance.media_new(file_path)
            player = self.vlc_instance.media_player_new()
            player.set_media(media)
            player_data['player'] = player  # Güncelle
            
            # Event manager'ları bağla (yeni player için)
            event_manager = player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_ended)
            event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_media_ended)
            
            # Volume ayarla
            player.audio_set_volume(int(self.global_volume * 100))
            
            # Play et
            result = player.play()
            if result == -1:
                error_msg = f"🎵 {name} oynatma başarısız (result: {result})"
                logging.error(error_msg)
                # Hata durumunda player'ı sıfırla
                media = self.vlc_instance.media_new(file_path)
                player = self.vlc_instance.media_player_new()
                player.set_media(media)
                player_data['player'] = player
                ee.emit("play_error", error_msg)
                self.is_playing = False
                self.currently_playing = None
                return False
            
            time.sleep(1.0)  # VLC yükleme için bekle
            state = player.get_state()
            if not player.is_playing() and state not in [vlc.State.Playing, vlc.State.Buffering]:
                logging.warning(f"⚠️ {name} play() sonrası is_playing() False – state: {state}")
                player.stop()
                player.release()
                player_data['player'] = None
                return False
            
            self.is_playing = True
            self.currently_playing = name
            logging.info(f"▶️ {name.capitalize()} çalınıyor (state: {state})")
            
            # Monitor thread'i başlat
            threading.Thread(
                target=self._monitor_playback,
                args=(player, name),
                daemon=True
            ).start()
            
            return True
        except Exception as e:
            error_msg = f"🎵 {name} çalma hatası: {str(e)}"
            logging.error(error_msg, exc_info=True)
            self.is_playing = False
            self.currently_playing = None
            ee.emit("play_error", error_msg)
            # Temizlik
            if 'player_data' in locals() and player_data['player']:
                try:
                    player_data['player'].stop()
                    player_data['player'].release()
                    player_data['player'] = None
                except:
                    pass
            return False


    def stop_all_media(self):
        """Tüm medyayı durdur - TELEGRAM UYUMLU GÜNCELLEME"""
        try:
            # ⚠️ Çift çağrı önleme
            if hasattr(self, '_stop_in_progress') and self._stop_in_progress:
                logging.debug("⏭️ Stop işlemi zaten devam ediyor, atlandı")
                return
                
            self._stop_in_progress = True
            logging.info("🔴 Tüm medya durduruluyor...")
            
            # İptal flag'ini set et
            self._cancellation_flag = True
            
            # Tüm player'ları durdur ve release et
            for name, player_data in list(self.players.items()):
                try:
                    player = player_data.get('player')
                    if player:
                        try:
                            player.stop()
                            # Kısa bekleme - VLC'nin tepki vermesi için
                            time.sleep(0.1)
                        except Exception as e:
                            if "access violation" not in str(e).lower():
                                logging.warning(f"⚠️ {name} stop hatası: {str(e)}")
                except Exception as e:
                    if "access violation" not in str(e).lower():
                        logging.warning(f"⚠️ {name} işlem hatası: {str(e)}")
            
            # Ek temizlik için bekleme
            time.sleep(0.2)
            
            # Release işlemleri
            for name, player_data in list(self.players.items()):
                try:
                    player = player_data.get('player')
                    if player:
                        try:
                            player.release()
                            logging.debug(f"🔓 {name} release edildi")
                        except Exception as e:
                            if "access violation" not in str(e).lower():
                                logging.warning(f"⚠️ {name} release hatası: {str(e)}")
                    player_data['player'] = None
                except Exception as e:
                    if "access violation" not in str(e).lower():
                        logging.warning(f"⚠️ {name} release işlem hatası: {str(e)}")
            
            # ⚠️ DURUMLARI KESİNLİKLE SIFIRLA
            self.is_playing = False
            self.currently_playing = None
            self.is_busy = False
            self.busy_message = ""
            
            # İptal flag'ini sıfırla
            self._cancellation_flag = False
            
            logging.info("✅ Tüm medya oynatıcıları durduruldu")
            
            # EVENT'leri yay - TELEGRAM DESTEKLİ
            try:
                self.loop.call_soon_threadsafe(
                    lambda: ee.emit("media_cancelled")
                )
                self.loop.call_soon_threadsafe(
                    lambda: ee.emit("media_ended", "forced_stop")
                )
                self.loop.call_soon_threadsafe(
                    lambda: ee.emit("all_media_stopped")  # YENİ EVENT
                )
            except Exception as e:
                logging.error(f"Event yayma hatası: {str(e)}")
                
        except Exception as e:
            logging.error(f"❌ Tüm medya durdurma hatası: {str(e)}", exc_info=True)
        finally:
            # İşlem tamamlandığında flag'i sıfırla
            self._stop_in_progress = False



    def _monitor_playback(self, player, name):
        """Oynatma durumunu izler - İYİLEŞTİRİLMİŞ"""
        try:
            # Medya yolunu al
            media_path = None
            try:
                media = player.get_media()
                if media:
                    media_path = media.get_mrl()
                    if media_path and media_path.startswith('file:///'):
                        media_path = media_path.replace('file:///', '')
            except Exception as e:
                logging.warning(f"Medya yolu alınamadı ({name}): {str(e)}")
            
            duration = 30  # Varsayılan süre
            if media_path and os.path.exists(media_path):
                try:
                    duration = get_duration(media_path)
                    logging.info(f"🎵 {name} için medya süresi: {duration} saniye")
                except Exception as e:
                    logging.warning(f"Süre hesaplanamadı ({name}): {str(e)}")
            
            # Oynatmanın başlamasını bekle
            start_time = time.time()
            max_wait_time = 10  # Maksimum bekleme süresini artır
            
            playback_started = False
            while time.time() - start_time < max_wait_time:
                try:
                    if player.is_playing():
                        playback_started = True
                        logging.info(f"▶️ {name} oynatma başladı")
                        break
                    time.sleep(0.1)
                except Exception as e:
                    logging.warning(f"Oynatıcı durumu kontrol hatası ({name}): {str(e)}")
                    break
            
            if not playback_started:
                logging.error(f"❌ {name} oynatma başlatılamadı")
                self._check_player_state(player, name)
                return
            
            # Oynatma süresince kontrol et
            playback_start = time.time()
            timeout = duration + 10  # 10 saniye tolerans
            
            while time.time() - playback_start < timeout:
                try:
                    state = player.get_state()
                    if state in [vlc.State.Ended, vlc.State.Stopped, vlc.State.Error]:
                        logging.info(f"⏹ {name} oynatması bitti (durum: {state})")
                        break
                    
                    # Player hala çalıyorsa devam et
                    if not player.is_playing():
                        # Kısa bir süre daha bekle
                        time.sleep(0.5)
                        if not player.is_playing():
                            logging.info(f"⏹ {name} oynatması durdu")
                            break
                    
                    time.sleep(0.1)
                except Exception as e:
                    logging.warning(f"Oynatıcı durumu kontrol hatası ({name}): {str(e)}")
                    break
            
            # Temizlik
            self._check_player_state(player, name)
            
        except Exception as e:
            logging.error(f"Oynatma izleme hatası ({name}): {str(e)}")
            self._check_player_state(player, name)
        
    def get_player(self, name):
        if name in self.players:
            player_data = self.players[name]
            if not player_data['player']:
                # Lazy yükle
                media = self.vlc_instance.media_new(player_data['path'])
                player = self.vlc_instance.media_player_new()
                player.set_media(media)
                player_data['player'] = player
                player_data['player'].audio_set_volume(int(self.global_volume * 100))
            return player_data['player']
        return None


    def _set_volumes(self):
        for name, player_data in self.players.items():  # player_data dictionary
            try:
                player = player_data.get('player')
                if player:  # Player varsa ses seviyesini ayarla
                    player.audio_set_volume(int(self.global_volume * 100))
                    logging.debug(f"Başlangıç ses seviyesi ayarlandı: {name}, {self.global_volume*100}%")
            except Exception as e:
                logging.error(f"Ses seviyesi ayarlama hatası ({name}): {str(e)}")

    def set_global_volume(self, volume_level):
        self.global_volume = max(0.0, min(1.0, volume_level))
        for name, player_data in self.players.items():
            try:
                player = player_data.get('player')
                if player:  # Player varsa ses seviyesini güncelle
                    player.audio_set_volume(int(self.global_volume * 100))
                    logging.debug(f"Ses seviyesi güncellendi: {name}, {self.global_volume*100}%")
            except Exception as e:
                logging.error(f"Ses güncelleme hatası ({name}): {str(e)}")
        
        self.loop.call_soon_threadsafe(
            lambda: ee.emit("volume_changed", self.global_volume * 100)
        )
        logging.info(f"Global ses seviyesi ayarlandı: {self.global_volume*100}%")
    
    def get_global_volume(self):
        """Global ses seviyesini döndürür"""
        if not hasattr(self, 'global_volume'):
            logging.warning("global_volume özniteliği eksik, varsayılan değere ayarlanıyor")
            self.global_volume = 0.8  # Varsayılan değer
        return self.global_volume
    
media_manager = MediaManager()


MODELS = {
    "male": {
        "onnx": "tr_TR-fahrettin-medium.onnx",
        "json": "tr_TR-fahrettin-medium.onnx.json"
    },
    "female": {
        # DİKKAT: Buradaki dosya ismi, erkek sesinden FARKLI olmalı.
        # İndirdiğin kadın sesi modelinin adını buraya yazmalısın.
        # Genellikle "tr_TR-dfki-medium" olarak iner.
        # Biz standart olsun diye adını değiştirmiş olabiliriz.
        "onnx": "tr_TR-dfki-medium.onnx", 
        "json": "tr_TR-dfki-medium.onnx.json"
    }
}

TTS_SETTINGS = {
    "cache_dir": "data/tts_cache",
    "output_file": "anons.wav",
    "use_cuda": False,
    "noise_scale": 0.667,
    "noise_w": 0.8,
}