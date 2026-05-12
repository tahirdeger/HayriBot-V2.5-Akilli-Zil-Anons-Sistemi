import logging
import re
import shutil
import sqlite3
from pathlib import Path
import sys
import os
import time
from .event_emitter import ee
from apscheduler.jobstores.base import JobLookupError
from tkinter import messagebox
from .path_resolver import get_data_path

_connection_closed = False  # Yeni global flag

def debug_ayarlar():
    """Ayarlar tablosundaki tüm kayıtları loglar"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute("SELECT * FROM ayarlar")
            rows = cursor.fetchall()
            if not rows:
                logging.info("Ayarlar tablosu boş")
            for row in rows:
                logging.info(f"Ayar: id={row[0]}, anahtar={row[1]}, deger={row[2]}")
    except sqlite3.Error as e:
        logging.error(f"Ayarlar debug hatası: {str(e)}", exc_info=True)

def check_db_schema():
    """Veritabanı şemasını kontrol eder ve gerekliyse düzeltir"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ayarlar'")
            if not cursor.fetchone():
                logging.warning("Ayarlar tablosu bulunamadı, oluşturuluyor...")
                conn.execute('''
                    CREATE TABLE ayarlar (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        anahtar TEXT NOT NULL UNIQUE,
                        deger TEXT
                    )
                ''')
                conn.commit()
                logging.info("Ayarlar tablosu oluşturuldu")
            
            # Varsayılan ayarları kontrol et ve ekle
            cursor = conn.execute("SELECT anahtar FROM ayarlar")
            existing_keys = {row[0] for row in cursor.fetchall()}
            default_settings = [
                ('telegram_api_key', ''),
                ('allowed_user_ids', ''),
                ('admin_chat_id', ''),
                ('startup_enabled', '0'),
                ('bells_enabled', '1'),
                ('school_type', 'normal'),
                ('startup_asked', '0'),
                ('school_name', ''),
                ('send_error_reports', '1'),
                ('user_email', ''),
                ('first_run', '1'),
                # --- YENİ EKLENENLER ---
                ('tts_speed', '1.0'),      # Varsayılan Hız: 1.0
                ('tts_model', 'male'),     # Varsayılan Ses: Erkek (Fahrettin)
            ]
            for anahtar, deger in default_settings:
                if anahtar not in existing_keys:
                    conn.execute(
                        "INSERT INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                        (anahtar, deger)
                    )
                    logging.info(f"Varsayılan ayar eklendi: {anahtar}={deger}")
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Şema kontrol hatası: {str(e)}", exc_info=True)
        raise


def get_school_type():
    """Kayıtlı okul türünü getir"""
    return ayar_getir("school_type", "normal")

def is_first_run() -> bool:
    """İlk çalıştırma kontrolü"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute(
                "SELECT deger FROM ayarlar WHERE anahtar = 'first_run'"
            )
            result = cursor.fetchone()
            if not result:
                # İlk çalıştırma, flag'i kaydet
                conn.execute(
                    "INSERT INTO ayarlar (anahtar, deger) VALUES ('first_run', '0')"
                )
                conn.commit()
                return True
            return False
    except sqlite3.Error as e:
        logging.error(f"İlk çalıştırma kontrol hatası: {str(e)}")
        return True  # Hata durumunda güvenli tarafta kal

DB_PATH = get_data_path("zil_db.sqlite")

def init_db():
    """Veritabanını başlat"""
    logging.info(f"Veritabanı başlatılıyor: {DB_PATH}")
    db_dir = DB_PATH.parent  # ← DEĞİŞTİR: Path.parent
    os.makedirs(db_dir, exist_ok=True)

    # .exe modunda veritabanı dosyasını kopyala (sadece yoksa)
    if not DB_PATH.exists() and getattr(sys, 'frozen', False):  # ← DEĞİŞTİR: Path.exists()
        # Eski sys._MEIPASS yerine resolver fallback kullan (ama _internal/data/ için)
        src_db = get_data_path("zil_db.sqlite")  # Resolver zaten _MEIPASS/data/zil_db.sqlite dener
        if src_db != DB_PATH and src_db.exists():  # Eğer farklıysa kopyala
            try:
                shutil.copy2(src_db, DB_PATH)
                logging.info(f"Veritabanı {DB_PATH} yoluna kopyalandı")
                os.chmod(DB_PATH, 0o666)  # Yazma izni ver
            except (IOError, OSError) as e:
                logging.error(f"Veritabanı kopyalama hatası: {str(e)}", exc_info=True)
                messagebox.showerror(  # Eski kod kalır
                    "Hata",
                    f"Veritabanı dosyası kopyalanamadı: {DB_PATH}\nLütfen uygulama dosyalarını kontrol edin."
                )
                sys.exit(1)
        else:
            logging.error(f"Kaynak veritabanı dosyası bulunamadı: {src_db}")
            messagebox.showerror(  # Eski kod kalır
                "Hata",
                f"Veritabanı dosyası bulunamadı: {src_db}\nLütfen uygulama dosyalarını kontrol edin."
            )
            sys.exit(1)

    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='zil_saatleri'")
            if not cursor.fetchone():
                conn.execute('''
                    CREATE TABLE zil_saatleri (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        saat TEXT NOT NULL,
                        tur TEXT NOT NULL 
                            DEFAULT 'ogrenci' 
                            CHECK (tur IN ('ogrenci', 'ogretmen', 'teneffus')),
                        aktif INTEGER DEFAULT 1,
                        job_id TEXT NOT NULL UNIQUE,
                        UNIQUE(saat, tur)
                    )''')
                conn.commit()
                logging.info("✅ Yeni zil_saatleri tablosu oluşturuldu")
        
        check_db_schema()
        logging.info("✅ Veritabanı başlatıldı")
        debug_ayarlar()
    except sqlite3.Error as e:
        logging.error(f"Veritabanı başlatılamadı: {str(e)}", exc_info=True)
        messagebox.showerror(
            "Hata",
            f"Veritabanı başlatılamadı: {str(e)}\nLütfen uygulama dosyalarını kontrol edin veya destek ekibiyle iletişime geçin."
        )
        raise

    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
            if not cursor.fetchone():
                conn.execute('''CREATE TABLE messages (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                chat_id TEXT NOT NULL,
                                message_id TEXT NOT NULL,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                            )''')
                logging.info("✅ Mesaj tablosu oluşturuldu")
    except sqlite3.Error as e:
        logging.error(f"Mesaj tablosu oluşturma hatası: {str(e)}")

def ekle_zil(saat: str, tur: str, job_id: str = None) -> bool:
    try:
        # Saat format kontrolü
        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', saat):
            logging.error(f"Geçersiz saat formatı: {saat}")
            return False

        # job_id yoksa otomatik oluştur
        if not job_id:
            job_id = f"{tur.lower()}_{saat.replace(':', '')}"
        
        logging.debug(f"Zil ekleme denemesi: saat={saat}, tur={tur}, job_id={job_id}")

        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO zil_saatleri (saat, tur, job_id) VALUES (?, ?, ?)",
                (saat, tur.lower(), job_id)
            )
            conn.commit()
            
            if cursor.rowcount > 0:
                ee.emit("veri_degisti")
                ee.emit("zil_eklendi", saat, tur.lower(), job_id)  # Yeni event
                logging.info(f"Zil eklendi: {saat}, {tur}, {job_id}")
                return True
            else:
                logging.warning(f"Zil eklenemedi: {saat}, {tur}, {job_id} - Satır etkilenmedi")
                return False
    except sqlite3.IntegrityError:
        logging.warning(f"Zaten kayıtlı: {saat}-{tur}")
        return False
    except sqlite3.Error as e:
        logging.error(f"Zil ekleme hatası: {str(e)}", exc_info=True)
        return False

def listele_zil():
    """Tüm zil saatlerini listeler"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute("""
                SELECT id, saat, tur, job_id 
                FROM zil_saatleri 
                WHERE aktif=1
                ORDER BY CAST(substr(saat,1,2) AS INTEGER), 
                         CAST(substr(saat,4,2) AS INTEGER)
            """)
            return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"Zil listeleme hatası: {str(e)}", exc_info=True)
        return []

def get_job_id(zil_id: int) -> str:
    """Zil ID'sine göre job_id getirir"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute(
                "SELECT job_id FROM zil_saatleri WHERE id=?",
                (zil_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Job ID alma hatası: {str(e)}", exc_info=True)
        return None

def sil_zil(zil_id: int) -> bool:
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id FROM zil_saatleri WHERE id=?", (zil_id,))
            job_id = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM zil_saatleri WHERE id=?", (zil_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                try:
                    from utils.scheduler import scheduler
                    scheduler.remove_job(job_id)
                    logging.info(f"🗑️ Scheduler job'ı silindi: {job_id}")
                except JobLookupError:  # ← Artık tanımlı
                    logging.warning(f"⚠️ Job zaten yok: {job_id}")
                
                ee.emit("veri_degisti")
                return True
            return False
    except sqlite3.Error as e:
        logging.error(f"❌ Silme hatası: {str(e)}")
        return False

def sil_tum_zil_saatleri() -> bool:
    """Tüm zil saatlerini siler"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM zil_saatleri")
            cursor.execute("UPDATE sqlite_sequence SET seq=0 WHERE name='zil_saatleri'")
            conn.commit()
            if cursor.rowcount > 0:
                ee.emit("veri_degisti")
                logging.info("✅ Tüm zil kayıtları silindi")
                return True
            return False
    except sqlite3.Error as e:
        logging.error(f"Toplu silme hatası: {str(e)}", exc_info=True)
        return False

def tablo_varmi() -> bool:
    """Tablo varlığını kontrol eder"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='zil_saatleri'")
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Tablo kontrol hatası: {str(e)}", exc_info=True)
        return False

def ayar_getir(anahtar: str, default_value: str = "") -> str:
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute(
                "SELECT deger FROM ayarlar WHERE anahtar = ?",
                (anahtar,)
            )
            result = cursor.fetchone()
            logging.debug(f"SQL Sorgusu: SELECT deger FROM ayarlar WHERE anahtar = '{anahtar}', Sonuç: {result}")
            value = result[0] if result else default_value
            logging.info(f"Ayar getirildi: {anahtar}={'[HIDDEN]' if anahtar == 'telegram_api_key' else value}")
            return value
    except sqlite3.Error as e:
        logging.error(f"Ayar getirme hatası: {anahtar}, Hata: {str(e)}", exc_info=True)
        return default_value

def ayar_kaydet(anahtar: str, deger: str) -> bool:
    try:
        with sqlite3.connect(DB_PATH, timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO ayarlar (anahtar, deger)
                VALUES (?, ?)
            ''', (anahtar, str(deger)))
            conn.commit()
            logging.info(f"Ayar kaydedildi: {anahtar}")
            return True
    except sqlite3.Error as e:
        logging.error(f"Ayar kaydetme hatası: {str(e)}", exc_info=True)
        return False

def close_db_connections():
    """Güvenli ve tek seferlik veritabanı kapatma"""
    global _connection_closed
    
    if not _connection_closed:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.close()
            _connection_closed = True
            logging.info("✅ Veritabanı bağlantıları tek seferde kapatıldı")
        except sqlite3.Error as e:
            logging.warning(f"⚠️ Veritabanı kapatma hatası: {str(e)}")
        except Exception as e:
            logging.error(f"Beklenmeyen kapatma hatası: {str(e)}")

def is_zil_exist(saat: str, tur: str) -> bool:
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.execute(
                "SELECT id FROM zil_saatleri WHERE saat=? AND tur=?",
                (saat, tur.lower())
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Zil çakışma kontrol hatası: {str(e)}", exc_info=True)
        return True  # Güvenli tarafta kalmak için
    

def ayar_guncelle(ayar_adi, yeni_deger):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE ayarlar SET deger = ? WHERE anahtar = ?",
                (yeni_deger, ayar_adi)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Ayar güncelleme hatası ({ayar_adi}): {str(e)}")
        return False
    
def is_bells_enabled() -> bool:
    """Zillerin aktif olup olmadığını kontrol eder"""
    try:
        value = ayar_getir("bells_enabled")
        return value == "1"
    except Exception as e:
        logging.error(f"Zil aktiflik kontrol hatası: {str(e)}", exc_info=True)
        return True  # Güvenli tarafta kalmak için varsayılan olarak aktif

def set_bells_enabled(enabled: bool) -> bool:
    """Zillerin aktiflik durumunu ayarlar"""
    try:
        success = ayar_kaydet("bells_enabled", "1" if enabled else "0")
        if success:
            logging.info(f"Ziller {'aktif' if enabled else 'pasif'} yapıldı")
            ee.emit("bells_enabled_changed", enabled)  # Durum değişikliğini bildir
            return True
        else:
            logging.error("Zil aktiflik durumu kaydedilemedi")
            return False
    except Exception as e:
        logging.error(f"Zil aktiflik ayarlama hatası: {str(e)}", exc_info=True)
        return False
    
