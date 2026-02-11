import os
import logging
import time
import wave
import sys
import threading

try:
    from piper import PiperVoice
except ImportError:
    logging.error("Piper TTS kütüphanesi yüklü değil!")
    PiperVoice = None

from config.settings import TTS_SETTINGS, MODELS
from utils.path_resolver import get_data_path
from utils.database import ayar_getir
from utils.event_emitter import ee

class PiperTTSManager:
    def __init__(self):
        self.use_cuda = False
        self.cache_dir = get_data_path("tts_cache")
        
        self.voice = None
        self.is_loaded = False
        self.current_model_type = None 
        
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Başlangıçta veritabanından tercihi oku ve yükle
        preferred_model = ayar_getir("tts_model", "male")
        # Başlangıçta sistemi kilitlememek için thread içinde gecikmeli başlat
        threading.Thread(target=self._delayed_startup, args=(preferred_model,), daemon=True).start()

        # Event dinleyici
        ee.on("tts_settings_changed", self.reload_model)

    def _delayed_startup(self, model_type):
        """Başlangıçta sistemi kilitlememek için gecikmeli yükleme"""
        logging.info("⏳ TTS modeli yüklemesi sistem açılışı için 15sn ertelendi...")
        time.sleep(15)
        self.load_model(model_type)

    def load_model(self, model_type="male"):
        """Belirtilen tipteki modeli yükler (male/female)"""
        if self.is_loaded and self.current_model_type == model_type:
            return True 
            
        try:
            logging.info(f"🔄 TTS Modeli yükleniyor: {model_type}")
            
            model_info = MODELS.get(model_type, MODELS.get("male"))
            
            # Yol oluşturma (Exe ve Python uyumlu)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                
            if not os.path.exists(os.path.join(base_dir, "models")):
                 if getattr(sys, 'frozen', False):
                     base_dir = os.path.join(os.path.dirname(sys.executable), "_internal")
            
            model_full_path = os.path.join(base_dir, "models", model_info["onnx"])
            config_full_path = os.path.join(base_dir, "models", model_info["json"])

            if not os.path.exists(model_full_path):
                base_dir = os.getcwd()
                model_full_path = os.path.join(base_dir, "models", model_info["onnx"])
                config_full_path = os.path.join(base_dir, "models", model_info["json"])

            if not os.path.exists(model_full_path):
                logging.error(f"❌ Model dosyası bulunamadı: {model_full_path}")
                if model_type != "male":
                    logging.warning("Seçilen model bulunamadı, varsayılan deneniyor...")
                    return self.load_model("male")
                return False

            self.voice = PiperVoice.load(
                model_full_path, 
                config_path=config_full_path,
                use_cuda=self.use_cuda
            )
            
            self.is_loaded = True
            self.current_model_type = model_type
            logging.info(f"✅ Piper TTS yüklendi: {model_type} ({self.voice.config.sample_rate} Hz)")
            ee.emit("tts_ready")
            return True
            
        except Exception as e:
            logging.error(f"Model yükleme hatası: {str(e)}")
            self.is_loaded = False
            return False

    def reload_model(self):
        target_model = ayar_getir("tts_model", "male")
        if target_model != self.current_model_type:
            self.load_model(target_model)

    def is_ready(self):
        return self.is_loaded

    def has_failed(self):
        return not self.is_loaded

    def synthesize_speech(self, text, output_filename="tts_temp.wav"):
        if not self.is_loaded:
            target = ayar_getir("tts_model", "male")
            if not self.load_model(target):
                return None

        try:
            output_path = os.path.join(self.cache_dir, output_filename)
            start_time = time.time()
            
            # --- HIZ AYARI ---
            try:
                user_speed = float(ayar_getir("tts_speed", "1.0"))
                if user_speed <= 0: user_speed = 1.0
                length_scale = 1.0 / user_speed
            except:
                length_scale = 1.0

            # Config ayarla
            if hasattr(self.voice, 'config'):
                self.voice.config.length_scale = length_scale
                self.voice.config.noise_scale = TTS_SETTINGS.get("noise_scale", 0.667)
                self.voice.config.noise_w = TTS_SETTINGS.get("noise_w", 0.8)

            # Dosyayı aç
            with wave.open(output_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(self.voice.config.sample_rate)
                
                # Sentezlemeyi başlat
                stream = self.voice.synthesize(text)
                
                chunks_written = 0
                
                for chunk in stream:
                    # 1. Eğer direkt bytes ise yaz
                    if isinstance(chunk, bytes):
                        wav_file.writeframes(chunk)
                        chunks_written += 1
                        continue
                    
                    # 2. Nesne ise, içindeki tüm özellikleri tara ve bytes olanı bul
                    # Bu yöntem nesne yapısı ne olursa olsun (audio, bytes, data, raw vs.) çalışır.
                    data_found = False
                    for attr_name in dir(chunk):
                        if attr_name.startswith('_'): continue # Gizli özellikleri geç
                        try:
                            val = getattr(chunk, attr_name)
                            if isinstance(val, bytes) and len(val) > 0:
                                wav_file.writeframes(val)
                                data_found = True
                                chunks_written += 1
                                break
                        except: pass
                    
                    if not data_found:
                        # Son çare: Belki nesnenin kendisi bytes'a dönüştürülebilir
                        try:
                            wav_file.writeframes(bytes(chunk))
                            chunks_written += 1
                        except: pass

            elapsed = time.time() - start_time
            file_size = os.path.getsize(output_path)
            logging.info(f"Ses üretildi ({elapsed:.2f}s, Hız: {user_speed}x, Boyut: {file_size}, Paketler: {chunks_written}): {output_path}")
            
            # WAV header 44 byte'tır. Dosya bundan büyükse ses verisi var demektir.
            if file_size > 44:
                return output_path
            else:
                logging.error(f"❌ Ses dosyası boş (Boyut: {file_size}). Text: '{text}'")
                return None

        except Exception as e:
            logging.error(f"Seslendirme hatası: {str(e)}", exc_info=True)
            return None

tts_manager = PiperTTSManager()