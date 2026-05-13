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
        self._failed = False          # Gerçek hata durumu — yükleniyor ≠ başarısız
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
        # UI'dan gelen görüntü isimlerini dahili anahtarlara çevir
        _normalize = {"erkek-fahrettin": "male", "kadin(yakinda)": "female",
                      "erkek": "male", "kadin": "female"}
        model_type = _normalize.get(model_type.lower(), model_type)

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
            self._failed = True
            ee.emit("tts_failed")
            return False

    def reload_model(self):
        target_model = ayar_getir("tts_model", "male")
        if target_model != self.current_model_type:
            self.load_model(target_model)

    def is_ready(self):
        return self.is_loaded

    def has_failed(self):
        return self._failed

    _ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
    _TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]

    @staticmethod
    def _sayi_oku(n: int) -> str:
        """0–999 arası sayıyı Türkçe okur."""
        if n == 0: return "sıfır"
        out = ""
        if n >= 100:
            out += ("" if n // 100 == 1 else PiperTTSManager._ONES[n // 100]) + "yüz"
            if n % 100: out += " "
            n %= 100
        if n >= 10:
            out += PiperTTSManager._TENS[n // 10]
            if n % 10: out += " "
            n %= 10
        if n:
            out += PiperTTSManager._ONES[n]
        return out.strip()

    @staticmethod
    def _preprocess(text: str) -> str:
        import re
        # Çoklu boşluk/satır sonu → tek boşluk
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n+", ". ", text)
        # Saat formatı: 08:30 → "sekiz otuz"
        def saat_oku(m):
            h, mn = int(m.group(1)), int(m.group(2))
            return PiperTTSManager._sayi_oku(h) + (" " + PiperTTSManager._sayi_oku(mn) if mn else "")
        text = re.sub(r"\b(\d{1,2}):(\d{2})\b", saat_oku, text)
        # Sayılar (0-999) → Türkçe kelime
        def sayi_cevir(m):
            n = int(m.group())
            return PiperTTSManager._sayi_oku(n) if n <= 999 else m.group()
        text = re.sub(r"\b\d+\b", sayi_cevir, text)
        # Noktalama düzenle
        text = re.sub(r"\.{2,}", ".", text)
        text = re.sub(r"\s+([.,!?])", r"\1", text)
        return text.strip()

    def synthesize_speech(self, text, output_filename="tts_temp.wav"):
        if not self.is_loaded:
            target = ayar_getir("tts_model", "male")
            if not self.load_model(target):
                return None

        try:
            text = self._preprocess(text)
            logging.debug(f"TTS önişlenmiş metin: {text}")

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