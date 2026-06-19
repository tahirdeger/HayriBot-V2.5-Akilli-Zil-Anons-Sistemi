#*gui/app.py*

from PIL import Image, ImageDraw
import pystray
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
import sys
import os
import psutil
import time
import subprocess
import shutil
import asyncio
from config.settings import media_manager, DB_PATH
from utils.path_resolver import get_media_path
import vlc
from utils.event_emitter import ee
from utils.database import (
    ekle_zil,
    sil_zil,
    listele_zil,
    ayar_getir,
    ayar_kaydet,
    close_db_connections,
    is_bells_enabled,
    set_bells_enabled
)
import re
import sqlite3
from utils.helpers import get_duration, restart_application
import webbrowser
import utils.tts_manager  # TTS sistemini arka planda başlatmak için


MEDIA_DIR = get_media_path()
LOCK_FILE = "app.lock"

class TelegramAyarlari(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.root = parent.winfo_toplevel()
        self.title("Telegram Ayarları")
        self.geometry("550x450")

        self.center_window()
        
        self.notebook = ttk.Notebook(self)
        
        self.api_frame = ttk.Frame(self.notebook)
        self._create_api_ui()
        
        self.tutorial_frame = ttk.Frame(self.notebook)
        self._create_tutorial_ui()
        
        self.notebook.add(self.api_frame, text="API Ayarları")
        self.notebook.add(self.tutorial_frame, text="Nasıl Yapılır?")
        self.notebook.pack(expand=True, fill=tk.BOTH)

    def center_window(self):
        """Pencereyi ekranın ortasına yerleştir"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _create_api_ui(self):
        lbl_api = ttk.Label(self.api_frame, text="Telegram API Key:")
        lbl_api.pack(pady=5)
        
        self.ent_api = ttk.Entry(self.api_frame, width=45)
        self.ent_api.insert(0, ayar_getir("telegram_api_key"))
        self.ent_api.pack(pady=5)
        
        lbl_users = ttk.Label(self.api_frame, text="İzin Verilen Kullanıcı ID'leri (Virgülle Ayırın):")
        lbl_users.pack(pady=5)
        
        self.txt_users = scrolledtext.ScrolledText(self.api_frame, height=4)
        self.txt_users.insert(tk.END, ayar_getir("allowed_user_ids"))
        self.txt_users.pack(pady=5, fill=tk.X, padx=10)
        
        btn_save = ttk.Button(
            self.api_frame,
            text="Tüm Ayarları Kaydet",
            command=self._ayar_kaydet
        )
        btn_save.pack(pady=5)

    def _create_tutorial_ui(self):
        text = """
        🔷 **Telegram API Nasıl Alınır?**
        1. Telegram'da @BotFather'a mesaj gönderin
        2. /newbot komutunu yazın
        3. Botunuza bir isim verin (Örn: OkulZilBot)
        4. Kullanıcı adı belirleyin (örnek: OkulZilBot)
        5. Size verilen API Key'i kopyalayın

        🔷 **Kullanıcı ID Nasıl Bulunur?**
        1. Telegramda @userinfobot'a mesaj gönderin
        2. /start komutunu yazın
        3. Size verilen ID'yi kopyalayın

        🔷 **API Key ve ID Nasıl Eklenir?**
        1. "API Ayarları" sekmesine geçin
        2. API Key'i ve ID'leri ilgili kutuya yapıştırın
        3. "Tüm Ayarları Kaydet" butonuna tıklayın ve uygulamayı yeniden başlatın.
        4.Telegram botunuza /start yazın

        ⚠️ **Güvenlik Uyarısı:**
        - API Key'inizi ve ID'nizi kimseyle paylaşmayın!
        """
        
        lbl = ttk.Label(
            self.tutorial_frame,
            text=text,
            font=("Segoe UI", 10),
            padding=15,
            wraplength=700,
            justify=tk.LEFT
        )
        lbl.pack()

    def _ayar_kaydet(self):
        api_key = self.ent_api.get().strip()
        user_ids = self.txt_users.get("1.0", tk.END).strip()
        
        if not api_key:
            logging.error("API Key boş bırakıldı")
            messagebox.showerror("Hata", "API Key boş bırakılamaz!")
            return
            
        try:
            logging.info(f"Kaydediliyor: telegram_api_key=[HIDDEN], allowed_user_ids={user_ids}")
            
            # Tek bir bağlantı ile tüm ayarları kaydet
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            
            # Mevcut ayarları kaydet
            cursor.execute(
                "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                ("telegram_api_key", api_key)
            )
            cursor.execute(
                "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?, ?)",
                ("allowed_user_ids", user_ids)
            )
            conn.commit()
            conn.close()
            
            # GUI'yi güncelle
            self.ent_api.delete(0, tk.END)
            self.ent_api.insert(0, api_key)
            self.txt_users.delete("1.0", tk.END)
            self.txt_users.insert("1.0", user_ids)
            
            # Başarı mesajı göster ve yeniden başlatma sorusu sor
            result = messagebox.askyesno(
                "Başarılı", 
                "Ayarlar başarıyla kaydedildi!\n"
                "Telegram botunun yeni ayarlarla başlatılması için uygulama yeniden başlatılacak.\n\n"
                "Yeniden başlatılsın mı?"
            )
            
            if result:
                self.destroy()
                # Ana pencere referansını al ve kapat
                root = self.root.winfo_toplevel()
                root.destroy()
                
                # GUI'yi güvenli kapat
                try:
                    root.update()
                    root.quit()
                except:
                    pass
                    
                # Yeniden başlat
                from utils.helpers import restart_application
                restart_application()
            else:
                messagebox.showinfo("Bilgi", "Ayarlar kaydedildi ancak yeniden başlatma iptal edildi. Değişiklikler uygulamayı yeniden başlattığınızda etkili olacak.")
                
        except sqlite3.Error as exc:
            logging.error(f"Ayar kaydetme hatası: {str(exc)}", exc_info=True)
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi: {str(exc)}")
        finally:
            try:
                close_db_connections()
                logging.debug("Veritabanı bağlantıları kapatıldı")
            except Exception as e:
                logging.error(f"Veritabanı bağlantısı kapatma hatası: {str(e)}")


# gui/app.py dosyasındaki AyarlarPaneli sınıfının YENİ HALİ

class AyarlarPaneli(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent  # Ana pencereyi referans olarak sakla
        self.title("Sistem Ayarları")
        self.geometry("550x550") # Biraz uzattık çünkü yeni ayarlar geldi

        self.center_window()
        
        # --- 1. OKUL TÜRÜ SEÇİMİ ---
        ttk.Label(self, text="Okul Türü:", font=("Segoe UI", 10, "bold")).pack(pady=(15, 5))
        
        self.school_type_var = tk.StringVar(value=ayar_getir("school_type", "normal"))
        school_frame = ttk.Frame(self)
        school_frame.pack(pady=5)
        
        ttk.Radiobutton(
            school_frame, 
            text="Normal Okul", 
            variable=self.school_type_var, 
            value="normal"
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Radiobutton(
            school_frame, 
            text="İmam Hatip Okulu", 
            variable=self.school_type_var, 
            value="imam_hatip"
        ).pack(side=tk.LEFT, padx=10)
        
        # --- 2. BAŞLANGIÇ AYARLARI ---
        separator = ttk.Separator(self, orient='horizontal')
        separator.pack(fill='x', pady=15, padx=10)
        
        ttk.Label(self, text="Başlangıç Ayarları:", font=("Segoe UI", 10, "bold")).pack(pady=(0, 5))
        
        self.startup_var = tk.BooleanVar(value=ayar_getir("startup_enabled") == "1")
        self._load_startup_setting()
        chk_startup = ttk.Checkbutton(
            self, 
            text="Windows başlangıcında otomatik başlat",
            variable=self.startup_var,
            command=self.update_startup_setting
        )
        chk_startup.pack(pady=5, padx=20, anchor="w")

        # --- 3. SESLENDİRME (TTS) AYARLARI [YENİ] ---
        separator2 = ttk.Separator(self, orient='horizontal')
        separator2.pack(fill='x', pady=15, padx=10)

        ttk.Label(self, text="Seslendirme Ayarları:", font=("Segoe UI", 10, "bold")).pack(pady=(0, 5))
        
        # A) Ses Modeli Seçimi
        frame_ses = ttk.Frame(self)
        frame_ses.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(frame_ses, text="🗣️ Seslendirmen:").pack(side=tk.LEFT)
        
        _model_display = {"male": "ERKEK", "female": "KADIN"}
        _current_db_model = ayar_getir("tts_model", "male")
        self.var_model = tk.StringVar(value=_model_display.get(_current_db_model, "ERKEK"))
        combo_model = ttk.Combobox(frame_ses, textvariable=self.var_model, state="readonly")
        combo_model['values'] = ('ERKEK', 'KADIN')
        combo_model.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(10,0))
        
        # B) Hız Ayarı
        frame_hiz = ttk.Frame(self)
        frame_hiz.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(frame_hiz, text="⚡ Konuşma Hızı:").pack(side=tk.LEFT)
        
        # Değer göstergesi (Örn: 1.0x)
        self.lbl_hiz_deger = ttk.Label(frame_hiz, text="1.0x")
        self.lbl_hiz_deger.pack(side=tk.RIGHT)
        
        # Slider (0.5 yavaş - 1.5 hızlı)
        try:
            current_speed = float(ayar_getir("tts_speed", "1.0"))
        except:
            current_speed = 1.0

        self.scale_hiz = ttk.Scale(self, from_=0.5, to=1.5, orient='horizontal', command=self._update_hiz_label)
        self.scale_hiz.set(current_speed)
        self.scale_hiz.pack(fill=tk.X, padx=20, pady=(5,0))
        
        # İlk açılışta etiketi güncelle
        self._update_hiz_label(current_speed)

        # --- KAYDET BUTONU ---
        ttk.Separator(self, orient='horizontal').pack(fill='x', pady=20, padx=10)
        
        ttk.Button(
            self, 
            text="💾 TÜM AYARLARI KAYDET", 
            command=self.save_all_settings,
            style="Success.TButton"
        ).pack(pady=10, ipadx=20, ipady=5)

    def center_window(self):
        """Pencereyi ekranın ortasına yerleştir"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _load_startup_setting(self):
        """Veritabanından mevcut ayarı yükler"""
        setting = ayar_getir("startup_enabled")
        self.startup_var.set(setting == "1")
    
    def _update_hiz_label(self, value):
        """Slider oynadıkça sağdaki yazıyı günceller"""
        val = round(float(value), 1)
        self.lbl_hiz_deger.config(text=f"{val}x")

    def update_startup_setting(self):
        """Başlangıç ayarını anlık uygular"""
        from utils.startup import add_to_startup, remove_from_startup
        try:
            success = False
            if self.startup_var.get():
                if add_to_startup():
                    success = ayar_kaydet("startup_enabled", "1")
            else:
                if remove_from_startup():
                    success = ayar_kaydet("startup_enabled", "0")

            if not success:
                self._load_startup_setting()
                messagebox.showerror("Hata", "Başlangıç ayarı kaydedilemedi! Yönetici izni gerekebilir.")
                
        except Exception as e:
            logging.error(f"Başlangıç ayarı hatası: {str(e)}", exc_info=True)
            self._load_startup_setting()
            messagebox.showerror("Hata", f"Beklenmeyen hata: {str(e)}")

    def save_all_settings(self):
        """Tüm ayarları (Okul Türü + TTS) kaydeder"""
        try:
            # 1. Okul Türü
            new_school_type = self.school_type_var.get()
            old_school_type = ayar_getir("school_type", "normal")
            
            # 2. TTS Ayarları — UI adını DB anahtarına çevir
            _model_to_key = {"ERKEK": "male", "KADIN": "female", "ERKEK-Fahrettin": "male", "KADIN(Yakında)": "female"}
            new_model_key = _model_to_key.get(self.var_model.get(), "male")
            new_speed = str(round(self.scale_hiz.get(), 1))

            # Veritabanına Kaydet
            k1 = ayar_kaydet("school_type", new_school_type)
            k2 = ayar_kaydet("tts_model", new_model_key)
            k3 = ayar_kaydet("tts_speed", new_speed)
            
            if k1 and k2 and k3:
                # TTS Yöneticisine haber ver (Anında uygula)
                from utils.event_emitter import ee
                ee.emit("tts_settings_changed")
                
                # Okul türü değiştiyse yeniden başlatma gerekir
                if new_school_type != old_school_type:
                    result = messagebox.askyesno(
                        "Yeniden Başlat", 
                        "✅ Ayarlar kaydedildi!\n\n"
                        "Okul türü değişikliğinin etkili olması için uygulamanın yeniden başlatılması gerekiyor.\n"
                        "Şimdi yeniden başlatılsın mı?"
                    )
                    if result:
                        self.restart_app_now()
                else:
                    messagebox.showinfo("Başarılı", "✅ Tüm ayarlar başarıyla kaydedildi ve uygulandı.")
                    self.destroy()
            else:
                messagebox.showerror("Hata", "Bazı ayarlar veritabanına yazılamadı!")
                
        except Exception as e:
            logging.error(f"Ayarları kaydetme hatası: {e}")
            messagebox.showerror("Hata", f"Kaydetme sırasında hata oluştu: {e}")

    def restart_app_now(self):
        """Uygulamayı güvenli şekilde yeniden başlatır"""
        self.destroy()
        self.parent.destroy()
        try:
            self.parent.update()
            self.parent.quit()
        except: pass
        
        from utils.helpers import restart_application
        restart_application()
    

class ZilYonetimGUI:
    def __init__(self, async_loop):
        self.root = tk.Tk()  # Yeni root nesnesi oluştur
        self.async_loop = async_loop
        self.volume_debounce_timer = None  # Debouncing için zamanlayıcı
        self.last_volume_value = media_manager.get_global_volume() * 100  # Başlangıç ses seviyesi
        
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        try:
            if getattr(sys, 'frozen', False):
                base_path = os.path.join(sys._MEIPASS, "..")
            else:
                base_path = os.path.dirname(os.path.dirname(__file__))
                
            icon_path = os.path.join(base_path, "media", "app_icon.ico")
            self.root.iconbitmap(icon_path)
            logging.info(f"İkon başarıyla yüklendi: {icon_path}")
        except Exception as e:
            logging.warning(f"İkon yüklenemedi: {str(e)}")
            self.root.iconbitmap(default='')

        self.root.title("HayriBot V1.4 Zil ve Duyuru Sistemi")
        self.root.geometry("1000x600")
        self.root.resizable(False, False)

        self.center_window()
        
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.selected = {}
        self.selected_items = set()
        
        self.style = self._setup_styles()
        
        self.volume_icon = None
        self.volume_scale = 100
        self.volume_percent = 100

        self.invalid_token_shown = False
        self.bells_enabled_var = tk.BooleanVar(value=is_bells_enabled())  # Zil aktiflik durumu
        # Buton durumlarını başlangıçta ayarla

        self._setup_main_layout()
        self._create_control_panel()
        self._setup_school_type_buttons()  # Okul türüne göre butonları ayarla
        self._create_inline_grid()
        self._create_status_bar()

        self._update_control_buttons_state(True)

        self.setup_event_listeners()
        self._configure_tags()
        self.create_telegram_settings_button()

        self._setup_school_type_buttons()  # Okul türüne göre butonları ayarla
        self._create_clock()
        self.tray_icon = None
        self.tray_thread = None

        BOT_TOKEN = ayar_getir("telegram_api_key")
        if (not BOT_TOKEN or BOT_TOKEN == "Api key giriniz") and not self.invalid_token_shown:
            self.btn_telegram.configure(state='normal')
            self.btn_seslendir.configure(state='disabled')
            self._update_status_with_style("⚠️ Telegram API anahtarı eksik!", "warning")  # DEĞİŞTİR
        else:
            self._update_status_with_style("✅ SİSTEM HAZIR", "normal")  # DEĞİŞTİR

        # Ağır işlemleri ertele (Başlangıçta donmayı önlemek için)
        self.root.after(500, self.listeyi_guncelle)

        # Başlangıçta olası kilitlenmeleri önlemek için temizlik (2 saniye sonra)
        self.root.after(2000, self._ensure_startup_clean)

        # Ses sistemini yenile ve ısıt (8 saniye sonra - Ses kartının hazır olması için süre uzatıldı)
        self.root.after(8000, self._warmup_audio_system)

        # Zamanlayıcı bekçisini başlat (30 saniyede bir kontrol et)
        self.root.after(30000, self._check_scheduler_status)

        # TTS yüklenene kadar seslendir butonunu pasif tut; durum etiketini izle
        self.btn_seslendir.configure(state='disabled')
        self.root.after(1000, self._poll_tts_status)

    def _warmup_audio_system(self):
        """VLC motorunu ve playerları yenileyerek başlangıç sorunlarını çöz"""
        def warmup_task():
            try:
                logging.info("🔥 Ses sistemi (VLC) yenileniyor...")
                
                # 1. DLL'leri yükle (Dummy instance)
                instance = vlc.Instance('--no-video --quiet')
                instance.release()
                
                # 2. MediaManager playerlarını yeniden oluştur
                # Bu işlem, boot sırasında ses kartı bulunamadıysa oluşan "bozuk" playerları düzeltir.
                media_files = {
                    'zil': 'zil.mp3',
                    'ogretmen_zil': "ogretmen_zil.mp3",
                    'teneffus_zil': "teneffus_zil.mp3",
                    'mars': 'istiklal.mp3',
                    'saygi': 'saygi.mp3',
                    'siren': 'siren.mp3',
                    'ezan': 'ezan.mp3',
                    'sela': 'sela.mp3',
                    'anons': 'anons.mp3',
                    'tekrar': 'tekrar.wav',
                    'startup': 'startup.wav'
                }
                
                if hasattr(media_manager, 'players'):
                    for key, filename in media_files.items():
                        try:
                            file_path = os.path.join(MEDIA_DIR, filename)
                            if os.path.exists(file_path):
                                # Varsa eski player'ı temizle
                                if key in media_manager.players:
                                    player_data = media_manager.players[key]
                                    # Yapının bozulmadığından emin ol (Dict kontrolü)
                                    if isinstance(player_data, dict):
                                        old_p = player_data.get('player')
                                        if isinstance(old_p, vlc.MediaPlayer):
                                            try: old_p.release()
                                            except: pass
                                        
                                        # Yeni player oluştur (Shared Instance ile)
                                        if hasattr(media_manager, 'vlc_instance'):
                                            media = media_manager.vlc_instance.media_new(file_path)
                                            new_player = media_manager.vlc_instance.media_player_new()
                                            new_player.set_media(media)
                                            player_data['player'] = new_player
                        except Exception as e:
                            logging.warning(f"Player yenileme uyarısı ({key}): {e}")

                    # Ses seviyelerini tekrar uygula
                    if hasattr(media_manager, '_set_volumes'):
                        media_manager._set_volumes()

                # 3. Başlangıç sesini çal (Sistemi tetikle)
                if hasattr(media_manager, 'play_media'):
                    # Meşguliyet varsa zorla temizle (Garanti olsun)
                    if media_manager.is_busy:
                        logging.info("🧹 Başlangıç öncesi meşguliyet temizleniyor...")
                        media_manager.set_busy_status(False, "")
                        
                    logging.info("🔊 Başlangıç sesi çalınıyor (Sistem Tetikleme)...")
                    media_manager.play_media('startup')

                logging.info("✅ Ses sistemi (VLC) ve Playerlar tamamen hazır")
            except Exception as e:
                logging.warning(f"Ses sistemi ısıtma uyarısı: {e}")
        
        threading.Thread(target=warmup_task, daemon=True).start()

    def _check_scheduler_status(self):
        """Zamanlayıcının çalışıp çalışmadığını kontrol et ve gerekirse başlat"""
        try:
            from utils.scheduler import scheduler
            if not scheduler.running:
                logging.warning("⚠️ UYARI: Zamanlayıcı durmuş! Otomatik olarak yeniden başlatılıyor...")
                try:
                    scheduler.start()
                    logging.info("✅ Zamanlayıcı yeniden başlatıldı.")
                except Exception as e:
                    logging.error(f"Zamanlayıcı başlatma hatası: {e}")
        except Exception as e:
            logging.error(f"Zamanlayıcı kontrol hatası: {e}")
        
        # Kendini tekrar planla
        self.root.after(30000, self._check_scheduler_status)

    def _poll_tts_status(self):
        """TTS yüklenme durumunu izler; etiket ve butonu günceller."""
        try:
            from utils.tts_manager import tts_manager
            if tts_manager.is_ready():
                self.lbl_tts_status.configure(
                    text="✅ Ses modeli hazır", foreground="#27ae60")
                self.btn_seslendir.configure(state='normal')
            elif tts_manager.has_failed():
                self.lbl_tts_status.configure(
                    text="❌ Ses modeli yüklenemedi — sesli duyuru devre dışı",
                    foreground="#c0392b")
                # Buton devre dışı kalır
            else:
                self.lbl_tts_status.configure(
                    text="⏳ Ses modeli yükleniyor...", foreground="#e67e22")
                self.btn_seslendir.configure(state='disabled')
                self.root.after(1000, self._poll_tts_status)
        except Exception:
            self.root.after(2000, self._poll_tts_status)

    def _ensure_startup_clean(self):
        """Başlangıçta sistemi temiz duruma getir"""
        try:
            # Eğer sistem meşgul görünüyorsa
            if media_manager.is_media_busy():
                logging.info("🛡️ Başlangıç koruması: Meşguliyet durumu sıfırlanıyor...")
                media_manager.stop_all_media()
                media_manager.is_busy = False
                media_manager.busy_message = ""
                media_manager.is_playing = False
                media_manager.currently_playing = None
                
                self._update_control_buttons_state(True)
                self.btn_seslendir.configure(state='normal')
                self._update_status_with_style("✅ Sistem Hazır", "normal")
        except Exception as e:
            logging.error(f"Başlangıç temizliği hatası: {e}")

    def center_window(self):
        """Pencereyi ekranın ortasına yerleştir"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")

    def _setup_school_type_buttons(self):
        """Okul türüne göre butonları göster/gizle"""
        from utils.database import ayar_getir
        
        school_type = ayar_getir("school_type", "normal")
        is_imam_hatip = school_type == "imam_hatip"
        
        # Ezan ve Sela butonlarını kontrol et
        for widget in self.control_frame.winfo_children():
            if isinstance(widget, ttk.Button):
                text = widget.cget("text")
                if "EZAN OKU" in text or "SELA OKU" in text:
                    if is_imam_hatip:
                        widget.pack(pady=1, fill=tk.X, padx=1)
                    else:
                        widget.pack_forget()


    def show_invalid_token_message(self):
        if not self.invalid_token_shown:
            self.invalid_token_shown = True
            
            dialog = tk.Toplevel(self.root)
            dialog.title("Kritik Hata")
            dialog.transient(self.root)
            dialog.grab_set()
            
            ttk.Label(dialog, 
                    text="Telegram API anahtarı geçersiz!\nLütfen Telegram Ayarları'ndan geçerli bir API anahtarı ve ID girin.", 
                    padding=10, 
                    foreground='red',
                    wraplength=300).pack(padx=10, pady=5)
            
            btn = ttk.Button(dialog, 
                            text="Tamam", 
                            command=lambda: self._on_dialog_close(dialog))
            btn.pack(pady=10)
            
            dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_dialog_close(dialog))

    def _on_dialog_close(self, dialog):
        dialog.grab_release()
        dialog.destroy()

    
    def create_tray_icon(self):
        """Sistem tepsisi ikonu oluştur"""
        try:
            icon_path = get_media_path("app_icon.ico")  # ← DEĞİŞTİR: Sadece .ico
            logging.debug(f"Sistem tepsisi ikonu yükleniyor: {icon_path}")
            
            if not icon_path.exists():
                logging.warning(f"İkon dosyası bulunamadı: {icon_path}, varsayılan ikon oluşturuluyor")
                img = Image.new('RGB', (64, 64), color='#2ecc71')
                d = ImageDraw.Draw(img)
                d.text((10, 25), "ZİL", fill='white')
                self.tray_icon = pystray.Icon("zil_sistemi", img, "Zil Yönetim Sistemi")
            else:
                image = Image.open(str(icon_path))
                self.tray_icon = pystray.Icon("zil_sistemi", image, "Zil Yönetim Sistemi")
            
            self.tray_icon.menu = pystray.Menu(
                pystray.MenuItem('Göster', self.restore_from_tray),
                pystray.MenuItem('Çıkış', self.kapat_uygulama)
            )
            
            if self.tray_icon:
                self.tray_icon.stop()
            
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()
            logging.info(f"Sistem tepsisi ikonu oluşturuldu: {icon_path}")
        except Exception as e:
            logging.error(f"Sistem tepsisi ikonu oluşturma hatası: {str(e)}", exc_info=True)
            messagebox.showwarning("Uyarı", f"Sistem tepsisi ikonu yüklenemedi: {str(e)}")
            # Varsayılan ikon
            img = Image.new('RGB', (64, 64), color='#2ecc71')
            d = ImageDraw.Draw(img)
            d.text((10, 25), "ZİL", fill='white')
            self.tray_icon = pystray.Icon("zil_sistemi", img, "Zil Yönetim Sistemi")
            self.tray_icon.menu = pystray.Menu(
                pystray.MenuItem('Göster', self.restore_from_tray),
                pystray.MenuItem('Çıkış', self.kapat_uygulama)
            )
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()

    def restore_from_tray(self, icon=None, item=None):
        """Sistem tepsisiinden geri getir"""
        try:
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None
            self.root.deiconify()
            self.root.after(0, self.root.lift)
        except Exception as e:
            logging.error(f"Geri getirme hatası: {str(e)}")
            self.root.deiconify()

    def sag_tik_menu(self, event):
        tree = event.widget
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def zili_sag_tikla_sil(self):
        focused_widget = self.root.focus_get()
        if isinstance(focused_widget, ttk.Treeview):
            selected_tree = focused_widget
            selected_item = selected_tree.selection()
            if selected_item:
                tur = None
                for key, tree in self.trees.items():
                    if tree == selected_tree:
                        tur = key
                        break
                if tur:
                    saat = selected_tree.item(selected_item[0])['values'][0]
                    zil_id = self._get_zil_id(saat, tur)
                    if zil_id and sil_zil(zil_id):
                        logging.info(f"GUI: Zil silindi: saat={saat}, tur={tur}, zil_id={zil_id}")
                        self.listeyi_guncelle()  # Doğrudan çağır
                        self.root.update_idletasks()  # GUI'yi zorla yenile
                        messagebox.showinfo("Başarılı", f"{saat} - {tur.capitalize()} zili silindi")
                        return
        messagebox.showwarning("Uyarı", "Lütfen silinecek zili sağ tıklayarak seçin!")

    def _create_volume_control(self):
        volume_control_frame = ttk.Frame(self.control_frame)
        volume_control_frame.pack(fill=tk.X, pady=2, padx=2)
        
        self.volume_icon = ttk.Label(volume_control_frame, text="🔊", width=3)
        self.volume_icon.pack(side=tk.LEFT, padx=(0, 2))
        
        self.volume_scale = ttk.Scale(
            volume_control_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            command=self._update_global_volume
        )
        self.volume_scale.set(self.last_volume_value)  # Başlangıç değerini ayarla
        self.volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.volume_percent = ttk.Label(volume_control_frame, text=f"%{int(self.last_volume_value)}", width=5)
        self.volume_percent.pack(side=tk.LEFT, padx=(2, 0))

    def _update_global_volume(self, value):
        """Ses seviyesini debouncing ile güncelle"""
        try:
            volume_level = float(value) / 100
            if abs(self.last_volume_value - (volume_level * 100)) < 1:  # Küçük değişiklikleri yoksay
                return
            if self.volume_debounce_timer:
                self.root.after_cancel(self.volume_debounce_timer)  # Önceki zamanlayıcıyı iptal et
            self.volume_debounce_timer = self.root.after(
                200,  # 200ms debouncing süresi
                lambda: self._apply_volume(volume_level)
            )
            logging.debug(f"Ses güncelleme planlandı: {volume_level*100}%")
        except ValueError as ve:
            logging.error(f"Ses güncelleme hatası (Geçersiz değer): {str(ve)}")
        except Exception as e:
            logging.error(f"Ses güncelleme hatası: {str(e)}", exc_info=True)

    def _apply_volume(self, volume_level):
        """Asıl ses seviyesini uygula"""
        try:
            media_manager.set_global_volume(volume_level)
            self.volume_percent.config(text=f"%{int(volume_level*100)}")
            self.volume_icon.config(text="🔊" if volume_level > 0 else "🔇")
            self.last_volume_value = volume_level * 100
            ee.emit("volume_changed", volume_level * 100)  # Olayı GUI'den tetikle
            logging.info(f"Ses seviyesi güncellendi: {volume_level*100}%")
        except Exception as e:
            logging.error(f"Ses uygulama hatası: {str(e)}", exc_info=True)
            self._update_status_with_style("⚠️ Ses seviyesi güncellenemedi", "warning")

    def _configure_tags(self):
        self.style.map("selected.Treeview",
            background=[('selected', '#E1F5FE'), ('!selected', '')])

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        
        style.configure("TButton", padding=3, font=("Segoe UI", 8))
        style.configure("Black.TButton",
            foreground="#ffffff",
            background="#000000",
            font=("Segoe UI", 8, "bold"),
            padding=5,
            relief="solid",
            borderwidth=1
        )
        style.map("Black.TButton",
            foreground=[('active', '#ffffff'), ('!active', '#ffffff')],
            background=[('active', '#333333'), ('!active', '#000000')]
        )
        style.map("Primary.TButton",
            foreground=[('active', '#ffffff'), ('!active', '#ffffff')],
            background=[('active', '#007bff'), ('!active', '#0069d9')]
        )
        style.configure("Success.TButton",
            foreground="#ffffff", background="#218838",
            font=("Segoe UI", 8, "bold"), padding=4, relief="flat"
        )
        style.map("Success.TButton",
            foreground=[('active', '#ffffff'), ('!active', '#ffffff')],
            background=[('active', '#28a745'), ('!active', '#218838')]
        )
        style.configure("Danger.TButton",
            foreground="#ffffff", background="#c82333",
            font=("Segoe UI", 8, "bold"), padding=4, relief="flat"
        )
        style.map("Danger.TButton",
            foreground=[('active', '#ffffff'), ('!active', '#ffffff')],
            background=[('active', '#dc3545'), ('!active', '#c82333')]
        )
        style.map("Warning.TButton",
            foreground=[('active', '#212529'), ('!active', '#212529')],
            background=[('active', '#ffd700'), ('!active', '#ffc107')]
        )
        style.map("Emergency.TButton",
            foreground=[('active', '#000000'), ('!active', '#000000')],
            background=[('active', '#FF4500'), ('!active', '#FF8C00')]
        )
        style.configure("Header.TLabelframe", 
            font=("Segoe UI", 8, "bold"),
            borderwidth=2,
            relief="groove",
            foreground="#2c3e50")
        style.configure("Info.TButton", 
            background="#D9E8FB",
            foreground="#2E5A8C")
        style.configure("Bold.TLabel", 
            font=("Segoe UI", 7, "bold"),
            foreground="#34495e")
        style.configure("evenrow.Treeview", 
            background="#e0e0e0")
        style.configure("oddrow.Treeview", 
            background="#ffffff")
        style.configure("selected.Treeview",
            background="#bbdefb")
        return style

    def _setup_main_layout(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.left_panel = ttk.Frame(self.main_frame, width=180)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=1)
        
        self.right_panel = ttk.Frame(self.main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=1)

    def _create_clock(self):
        clock_frame = ttk.Frame(self.left_panel)
        clock_frame.pack(fill=tk.X, padx=2, pady=2)
        
        self.clock_bar = ttk.Label(
            clock_frame,
            font=("Segoe UI", 8, "bold"),
            foreground="#2c3e50",
            background="#f0f0f0",
            anchor=tk.CENTER
        )
        self.clock_bar.pack(fill=tk.X)
        self.update_clock()

    def update_clock(self):
        current_time = time.strftime("%d/%m/%Y %H:%M:%S")
        self.clock_bar.config(text=current_time)
        self.root.after(1000, self.update_clock)

    def _create_control_panel(self):
        self.control_frame = ttk.LabelFrame(
            self.left_panel,
            text="🎛️ KONTROL PANELİ",
            style="Header.TLabelframe"
        )
        self.control_frame.pack(fill=tk.X, pady=1, padx=1)
        
        self._create_volume_control()
        
        buttons = [
            ("🔔 ÖĞRENCİ ZİLİ", "ogrenci_zil", "Primary.TButton"),
            ("👩🏫 ÖĞRETMEN ZİLİ", "ogretmen_zil", "Primary.TButton"),  # YENİ
            ("🚪 ÇIKIŞ ZİLİ", "cikis_zil", "Primary.TButton"),        # YENİ
            ("🎵 İSTİKLAL MARŞI", "mars", "Success.TButton"),
            ("🕯️ SAYGI DURUŞU", "saygi", "Warning.TButton"),
            ("🚨 ACİL SİREN", "siren", "Emergency.TButton"),
            ("🕌 EZAN OKU", "ezan", "Info.TButton"),
            ("🕌 SELA OKU", "sela", "Info.TButton"),
        ]
        
        # Buton listesini sakla
        self.control_frame.btn_list = []
        
        for text, cmd, style in buttons:
            btn = ttk.Button(
                self.control_frame,
                text=text,
                command=lambda c=cmd: self._handle_control(c),
                style=style,
                width=15
            )
            # Butonları listeye ekle, okul türüne göre ayarlanacak
            self.control_frame.btn_list.append((btn, text))
            
            # Normal butonları hemen göster, Ezan/Sela sonra ayarlanacak
            if "EZAN" not in text and "SELA" not in text:
                btn.pack(pady=1, fill=tk.X, padx=1)
        
        # Zil Aç/Kapa Butonu
        self.btn_toggle_bells = ttk.Button(
            self.control_frame,
            text="Zilleri Kapat",
            style="Warning.TButton",
            command=self.toggle_bells
        )
        self.btn_toggle_bells.pack(fill=tk.X, pady=2)
        self._update_toggle_button()

        # "SESLERİ DURDUR" butonunu güncelle
        ttk.Button(
            self.control_frame,
            text="⏹ TÜM SESLERİ DURDUR",
            command=self._stop_all_media_gui,
            style="Danger.TButton"
        ).pack(pady=1, fill=tk.X, padx=1)

        ttk.Button(
            self.control_frame,
            text="⛔ UYGULAMAYI KAPAT",
            command=self.kapat_uygulama,
            style="Danger.TButton",
            width=11
        ).pack(pady=2, fill=tk.X, padx=1)
        
        text_frame = ttk.LabelFrame(
            self.left_panel,
            text="📢 DUYURU SİSTEMİ",
            style="Header.TLabelframe"
        )
        text_frame.pack(fill=tk.X, pady=1, padx=1)
        
        self.text_input = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            height=4,
            padx=2,
            pady=2
        )
        self.text_input.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(text_frame)
        btn_frame.pack(pady=1)
        
        self.btn_seslendir = ttk.Button(
            btn_frame,
            text="▶️ Seslendir",
            command=self.seslendir_metin,  # Direkt seslendir_metin'i çağır
            style="Success.TButton"
        )
        self.btn_seslendir.pack(side=tk.LEFT, padx=1)

        
        
        ttk.Button(
            btn_frame,
            text="🗑️Temizle",
            command=lambda: self.text_input.delete("1.0", tk.END),
            style="Danger.TButton"
        ).pack(side=tk.RIGHT, padx=1)

        # TTS durum etiketi
        self.lbl_tts_status = ttk.Label(
            text_frame,
            text="⏳ Ses modeli yükleniyor...",
            font=("Segoe UI", 7, "italic"),
            foreground="#e67e22"
        )
        self.lbl_tts_status.pack(pady=(0, 2))



    def kapat_uygulama(self):
        if messagebox.askyesno("Çıkış Onayı", "Uygulamayı kapatmak istediğinizden emin misiniz?"):
            try:
                media_manager.stop_all_media()
                active_threads = [t for t in threading.enumerate() 
                                if t != threading.main_thread()]
                for t in active_threads:
                    if not t.daemon:
                        t.join(timeout=0.5)
                        logging.info(f"Thread sonlandırıldı: {t.name}")
                if self.tray_icon:
                    self.tray_icon.stop()
                    self.tray_icon = None
                if os.path.exists(LOCK_FILE):
                    try:
                        os.remove(LOCK_FILE)
                        logging.info("Kilit dosyası silindi (kapat_uygulama).")
                    except Exception as e:
                        logging.error(f"Kilit dosyası silinemedi (kapat_uygulama): {str(e)}")
                current_pid = os.getpid()
                exe_name = "main.exe" if getattr(sys, 'frozen', False) else os.path.basename(sys.argv[0])
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.name() == exe_name and proc.pid != current_pid:
                        proc.terminate()
                        logging.info(f"Diğer süreç sonlandırıldı (PID: {proc.pid}).")
                self.root.quit()
                self.root.destroy()
                os._exit(0)
            except Exception as e:
                logging.critical(f"Kritik çıkış hatası: {e}")
                os._exit(1)


    def _stop_all_media_gui(self):
        """GUI'den tüm sesleri durdur - GÜÇLENDİRİLMİŞ VERSİYON"""
        try:
            logging.info("🔴 GUI: Tüm sesleri durdur butonuna basıldı")
            
            from config.settings import media_manager
            
            # MediaManager üzerinden durdur
            media_manager.stop_all_media()
            
            # Event yay
            ee.emit("stop_all_media", {
                'source': 'gui', 
                'timestamp': time.time()
            })
            
            # GUI durumunu hemen güncelle (gecikme olmadan)
            self._update_control_buttons_state(True)
            self.btn_seslendir.configure(state='normal')
            self._update_status_with_style("✅ Tüm sesler durduruldu", "normal")
            
            # Buton durumunu zorla güncelle
            self.root.update_idletasks()
            
            logging.info("✅ GUI: Tüm sesler durduruldu")
            
        except Exception as e:
            logging.error(f"❌ GUI durdurma hatası: {str(e)}", exc_info=True)
            self._update_status_with_style("❌ Sesler durdurulamadı!", "error")


    def minimize_to_tray(self):
        """Pencereyi sistem tepsisine küçült"""
        self.root.withdraw()
        if self.tray_icon:
            self.tray_icon.stop()
        self.create_tray_icon()


    def _handle_control(self, command):
        from config.settings import media_manager
        
        # Tüm sesleri durdur ve iptal et
        if command == "stop_all":
            media_manager.cancel_all_operations()
            self._update_status_with_style("⏹ Tüm sesler durduruldu ve iptal edildi", "normal")
            # Butonları hemen aktif yap (sadece çalma butonları)
            self._update_control_buttons_state(True)
            self.btn_seslendir.configure(state='normal')
            return
        
        # Meşguliyet kontrolü ekle (diğer komutlar için)
        if media_manager.is_media_busy():
            busy_message = media_manager.get_busy_message()
            self._update_status_with_style(f"⚠️ Şu anda {busy_message} çalıyor. Lütfen bekleyin...", "warning")
            return
            
        if command == "stop_all":
            media_manager.stop_all_media()
            self._update_status_with_style("⏹ Tüm sesler durduruldu ve kuyruk temizlendi", "normal")
        else:
            # Zil türlerini kontrol et
            if command == "ogrenci_zil":
                media_type = "zil"
                display_name = "Öğrenci Zili"
            elif command == "ogretmen_zil":
                media_type = "ogretmen_zil"
                display_name = "Öğretmen Zili"
            elif command == "cikis_zil":
                media_type = "teneffus_zil"
                display_name = "Çıkış Zili"
            elif command == "mars":
                media_type = "mars"
                display_name = "İstiklal Marşı"
            elif command == "saygi":
                media_type = "saygi"
                display_name = "Saygı Duruşu"
            elif command == "siren":
                media_type = "siren"
                display_name = "Acil Siren"
            elif command == "ezan":
                media_type = "ezan"
                display_name = "Ezan"
            elif command == "sela":
                media_type = "sela"
                display_name = "Sela"
            else:
                media_type = command
                display_name = command.capitalize()
                
            # UI'da hemen geri bildirim ver ve kilit koy (Çoklu tıklamayı ve yığılmayı önle)
            self._update_control_buttons_state(False)
            self.btn_seslendir.configure(state='disabled')
            self._update_status_with_style(f"⏳ {display_name} hazırlanıyor...", "warning")

            # Medyayı çal
            # GUI donmasını önlemek için thread içinde çalıştır
            def run_play():
                try:
                    # Retry mekanizması: 3 deneme, her biri arasında 1 saniye bekle
                    success = False
                    for i in range(3):
                        if media_manager.play_media(media_type):
                            success = True
                            break
                        logging.warning(f"⚠️ {display_name} çalma denemesi {i+1}/3 başarısız, bekleniyor...")
                        time.sleep(1.0)

                    if success:
                        self.root.after(0, lambda: self._update_status_with_style(f"▶️ {display_name} çalınıyor...", "normal"))
                    else:
                        self.root.after(0, lambda: self._update_status_with_style(f"❌ {display_name} çalınamadı", "error"))
                        # Hata durumunda butonları geri aç
                        self.root.after(0, lambda: self._update_control_buttons_state(True))
                        self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
                except Exception as e:
                    logging.error(f"Play thread error: {e}")
                    self.root.after(0, lambda: self._update_status_with_style(f"❌ Hata: {str(e)}", "error"))
                    self.root.after(0, lambda: self._update_control_buttons_state(True))
                    self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
            
            threading.Thread(target=run_play, daemon=True).start()

    def _create_inline_grid(self):
        """Sağ panele doğrudan 14×3 Entry grid yerleştirir."""
        TURLER = ["ogrenci", "ogretmen", "teneffus"]
        BASLIKLAR = ["Öğrenci", "Öğretmen", "Teneffüs"]
        SAAT_RE = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')

        # --- Üst buton çubuğu ---
        btn_frame = ttk.Frame(self.right_panel)
        btn_frame.pack(fill=tk.X, pady=(2, 0), padx=2)

        ttk.Button(btn_frame, text="💾 Kaydet",
                   command=self._save_grid,
                   style="Success.TButton").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="🗑 Tümünü Sil",
                   command=self.sil_tum_zil_saatleri,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=4)
        ttk.Label(btn_frame,
                  text="Boş satırlar atlanır  |  Format: SS:DD (örn: 08:30)",
                  font=("Segoe UI", 7), foreground="#555").pack(side=tk.RIGHT, padx=6)

        # --- Grid çerçevesi ---
        outer = ttk.LabelFrame(self.right_panel,
                               text="📋 DERS ZİL SAATLERİ PLANI",
                               style="Header.TLabelframe")
        outer.pack(fill=tk.BOTH, expand=True, pady=(2, 1), padx=2)

        # Başlık satırı
        hdr = ttk.Frame(outer)
        hdr.pack(fill=tk.X, padx=4, pady=(4, 1))
        hdr.columnconfigure(0, minsize=32)
        for c in range(1, 4):
            hdr.columnconfigure(c, weight=1)

        ttk.Label(hdr, text="No", font=("Segoe UI", 8, "bold"),
                  anchor="center").grid(row=0, column=0, padx=2)
        for c, b in enumerate(BASLIKLAR, 1):
            ttk.Label(hdr, text=b, font=("Segoe UI", 8, "bold"),
                      anchor="center").grid(row=0, column=c, padx=2, sticky="ew")

        ttk.Separator(outer, orient="horizontal").pack(fill=tk.X, padx=4)

        # Veri satırları
        rows_frame = ttk.Frame(outer)
        rows_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        rows_frame.columnconfigure(0, minsize=32)
        for c in range(1, 4):
            rows_frame.columnconfigure(c, weight=1)

        self.grid_entries = []
        for row in range(14):
            bg = "#eef2ff" if row % 2 == 0 else "#ffffff"
            ttk.Label(rows_frame, text=f"{row+1:2d}.",
                      font=("Segoe UI", 8), anchor="e",
                      background=bg).grid(row=row, column=0, padx=(2, 4), pady=2, sticky="e")
            row_entries = {}
            for c, tur in enumerate(TURLER, 1):
                e = ttk.Entry(rows_frame, font=("Segoe UI", 9), justify="center")
                e.grid(row=row, column=c, padx=3, pady=2, sticky="ew")
                e.bind("<Return>", lambda ev: ev.widget.tk_focusNext().focus())
                row_entries[tur] = e
            self.grid_entries.append(row_entries)

        # Kaydet kısayolu: Ctrl+S
        self.root.bind("<Control-s>", lambda e: self._save_grid())

        # Eski tree referanslarının null guard'ı (event'ler için)
        self.trees = {}
        self.numara_tree = None

    def _toggle_selection(self, event, tur):
        pass  # Treeview kaldırıldı

    def _scroll_all(self, *args):
        pass  # Treeview kaldırıldı

    def _create_edit_panel(self):
        pass  # Butonlar _create_inline_grid içine taşındı

    def _create_status_bar(self):
        footer_frame = ttk.Frame(self.root)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_bar = ttk.Label(
            footer_frame,
            text="✅ SİSTEM HAZIR",
            font=("Segoe UI", 8, "bold"),
            foreground="#ffffff",
            background="#2ecc71",
            padding=(5, 2)
        )
        self.status_bar.pack(side=tk.LEFT, padx=5)
        
        # Tıklanabilir bağlantı
        link_label = ttk.Label(
            footer_frame,
            text="HayriBotV2 | 2025 | zamanmakinesi.xyz",
            font=("Segoe UI", 9, "italic", "underline"),
            foreground="#0000FF",
            cursor="hand2",
            padding=(0, 0, 10, 0)
        )
        link_label.pack(side=tk.RIGHT, anchor='se')
        
        # Bağlantıya tıklama olayı bağla
        link_label.bind("<Button-1>", lambda event: webbrowser.open("https://islematolyesi.odoo.com/blog/verimlilik-araclari-4/hayribot-zil-ve-duyuru-sistemi-10"))

    def _update_status(self, message, status_type="normal"):
        """Durum çubuğunu günceller (geriye uyumluluk için)"""
        self._update_status_with_style(message, status_type)
    
    def _update_status_with_style(self, message, status_type="normal"):
        """Durum çubuğunu stil ile günceller"""
        colors = {
            "normal": ("#ffffff", "#2ecc71"),  # Beyaz yazı, yeşil arkaplan
            "warning": ("#000000", "#f39c12"),  # Siyah yazı, turuncu arkaplan
            "connected": ("#ffffff", "#27ae60"),  # Beyaz yazı, koyu yeşil
            "disconnected": ("#ffffff", "#e74c3c"),  # Beyaz yazı, kırmızı
            "error": ("#ffffff", "#c0392b")  # Beyaz yazı, koyu kırmızı
        }
        
        fg_color, bg_color = colors.get(status_type, ("#ffffff", "#2ecc71"))
        
        self.status_bar.config(
            text=message,
            foreground=fg_color,
            background=bg_color
        )
        self.root.update_idletasks()

    # Sistem ayarları butonunun command kısmını güncelle
    def create_telegram_settings_button(self):
        btn_frame = ttk.Frame(self.left_panel)
        btn_frame.pack(pady=5, fill=tk.X)
        
        self.btn_telegram = ttk.Button(
            btn_frame,
            text="⚙ Telegram Ayarları",
            command=self.open_telegram_settings,
            style="Info.TButton"
        )
        self.btn_telegram.pack(side=tk.RIGHT, expand=True, padx=1)
        
        ttk.Button(
            btn_frame,
            text="🔊Zil Sesi Değiştir",
            command=self.zil_sesi_degistir,
            style="Info.TButton"
        ).pack(side=tk.LEFT, expand=True, padx=1)

        # Bu satırı GÜNCELLE - lambda yerine doğrudan metod çağrısı
        ttk.Button(
            btn_frame,
            text="⚙ Sistem Ayarları",
            command=self.open_system_settings,  # Yeni metod
            style="Info.TButton"
        ).pack(side=tk.LEFT, expand=True, padx=1)

    # Yeni metod ekle
    def open_system_settings(self):
        """Sistem ayarları penceresini açar"""
        AyarlarPaneli(self.root)

    def open_telegram_settings(self):
        TelegramAyarlari(self.root)

    async def play_media_async(self, media_type):
        try:
            self.log_system_resources()
            logging.debug(f"Medya oynatma başlatılıyor: {media_type}")
            result = media_manager.play_media(media_type)
            if not result:
                return
            media_files = {
                'zil': 'zil.mp3',
                'ogretmen_zil': "ogretmen_zil.mp3",
                'teneffus_zil': "teneffus_zil.mp3",
                'mars': 'istiklal.mp3',
                'saygi': 'saygi.mp3',
                'siren': 'siren.mp3',
                'ezan': 'ezan.mp3',
                'sela': 'sela.mp3',
                'anons': 'anons.mp3',
                'tekrar': 'tekrar.wav'
            }
            media_path = os.path.join(MEDIA_DIR, media_files.get(media_type))
            if not os.path.exists(media_path):
                error_msg = f"Medya dosyası bulunamadı: {media_path}"
                logging.error(error_msg)
                ee.emit("play_error", error_msg)
                return
            duration = get_duration(media_path)
            await asyncio.sleep(duration + 1)
            logging.info(f"{media_type} oynatıldı")
        except Exception as exc:
            logging.error(f"Oynatma hatası: {str(exc)}", exc_info=True)
            ee.emit("play_error", f"Oynatma hatası: {str(exc)}")

    def play_media(self, media_type):
        if self.confirm_action(f"{media_type.capitalize()} çalma"):
            threading.Thread(
                target=self._play_media_thread,
                args=(media_type,),
                daemon=True
            ).start()

    def _play_media_thread(self, media_type):
        try:
            future = asyncio.run_coroutine_threadsafe(self.play_media_async(media_type), self.async_loop)
            future.result()
            self.log_system_resources()
        except Exception as exc:
            logging.error(f"Medya oynatma thread hatası: {str(exc)}", exc_info=True)
            ee.emit("play_error", f"Medya oynatma hatası: {str(exc)}")

    def stop_media(self, media_type):
        try:
            player = media_manager.get_player(media_type)
            if player:
                player.stop()
                logging.info(f"Medya durduruldu: {media_type}")
        except Exception as e:
            logging.error(f"Durdurma hatası: {str(e)}")
            ee.emit("play_error", f"Durdurma hatası: {str(e)}")

    def log_system_resources(self):
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            logging.info(f"Kaynak Kullanımı - CPU: {cpu_percent}%, Bellek: {memory.percent}%")
        except Exception as e:
            logging.error(f"Kaynak izleme hatası: {str(e)}")


    async def seslendir_metin_async(self, metin, chat_id=None):
        from utils.tts_manager import tts_manager
        from utils.helpers import validate_audio_file
        import re
        
        chat_id=chat_id
        # Meşguliyet kontrolü ekle
        if media_manager.is_media_busy():
            busy_message = media_manager.get_busy_message()
            self._update_status_with_style(f"⚠️ Şu anda {busy_message} çalıyor. Lütfen bekleyin...", "warning")
            
            # Telegram'a bildirim gönder
            if chat_id:
                ee.emit("telegram_duyuru_durumu", {
                    "durum": "uyari",
                    "mesaj": f"Şu anda {busy_message} çalıyor. Lütfen bekleyin...",
                    "chat_id": chat_id
                })
            return
        
        # İptal flag'ini BAŞLANGIÇTA sıfırla
        media_manager.reset_cancellation()  # ← ÖNEMLİ: Başlangıçta sıfırla
        tmpfile = None
        tts_media_name = 'tts_temp'
        
        # Metni ön-işle
        metin = re.sub(r'\.+', '.', metin).rstrip('.').strip() + ('.' if metin and metin[-1].isalnum() else '')
        logging.info(f"Ön-işlenmiş metin: {metin}")
        

        try:
            # Meşguliyet durumunu ayarla
            media_manager.set_busy_status(True, "Telegram Duyurusu" if chat_id else "Metin Seslendirme")

            logging.debug("Seslendirme işlemi başlatılıyor (XTTS v2)")
            
            
            # Tüm iptal kontrollerini GÜNCELLE:
            if media_manager.is_cancelled():
                logging.info("🔴 İşlem başlangıçta iptal edildi")
                raise Exception("İşlem kullanıcı tarafından iptal edildi")
            
            timeout = 30
            start_time = time.time()
            while not tts_manager.is_ready() and not tts_manager.has_failed():
                # İptal kontrolü - TTS yüklenme sırasında
                if media_manager.is_cancelled():
                    logging.info("🔴 TTS yüklenme sırasında iptal edildi")
                    raise Exception("İşlem kullanıcı tarafından iptal edildi")
                    
                if (time.time() - start_time) > timeout:
                    raise Exception("TTS modeli zaman aşımına uğradı")
                await asyncio.sleep(0.5)
            
            if tts_manager.has_failed():
                raise Exception("TTS modeli yüklenemedi")
            
            if not tts_manager.is_ready():
                raise Exception("TTS modeli hazır değil")

            # 2. METINDEN SESE DÖNÜŞTÜRME
            self._update_status_with_style(f"🗣️ {len(metin)} karakter seslendiriliyor...", "normal")

            if chat_id:
                ee.emit("telegram_duyuru_durumu", {
                    "durum": "bilgi",
                    "mesaj": "Karakterler ayrıştırılıyor... Lütfen bekleyin!",
                    "chat_id": chat_id
                })

            # İptal kontrolü - TTS sentezleme öncesi
            if media_manager.is_cancelled():
                logging.info("🔴 TTS sentezleme öncesi iptal edildi")
                raise Exception("İşlem kullanıcı tarafından iptal edildi")

            tmpfile = tts_manager.synthesize_speech(metin)
            
            # İptal kontrolü - TTS sentezleme sonrası
            if media_manager.is_cancelled():
                logging.info("🔴 TTS sentezleme sonrası iptal edildi")
                raise Exception("İşlem kullanıcı tarafından iptal edildi")
            
            is_valid, message = validate_audio_file(tmpfile)
            if not is_valid:
                raise Exception(f"Ses dosyası geçersiz: {message}")
            
            text_duration = get_duration(tmpfile)
            logging.info(f"TTS ses süresi: {text_duration}s")
            
            # TTS sesini MediaManager'a ekle
            media_manager.players[tts_media_name] = {'path': tmpfile, 'player': None}
            
            # 3. ANONS.MP3
            self._update_status_with_style("🔊 Anons sesi çalınıyor...", "normal")

            media_manager.stop_all_media()
            await asyncio.sleep(1.0)
            
            # İptal kontrolü - Anons öncesi
            if media_manager.is_cancelled():
                logging.info("🔴 Anons öncesi iptal edildi")
                raise Exception("İşlem kullanıcı tarafından iptal edildi")
            
            # MediaManager üzerinden anons çal
            anons_result = media_manager.play_media('anons')
            if not anons_result:
                raise Exception("Anons sesi çalınamadı")
            
            # Anons sırasında iptal kontrolü
            anons_path = os.path.join(MEDIA_DIR, "anons.mp3")
            anons_duration = get_duration(anons_path)
            logging.info(f"Anons süresi: {anons_duration}s")
            
            # Anons boyunca iptal kontrolü
            anons_start = time.time()
            while (time.time() - anons_start) < (anons_duration + 0.5):  # +2 saniye tolerans
                if media_manager.is_cancelled():
                    logging.info("🔴 Anons sırasında iptal edildi")
                    media_manager.stop_all_media()
                    raise Exception("İşlem kullanıcı tarafından iptal edildi")
                await asyncio.sleep(0.1)

            if chat_id:
                ee.emit("telegram_duyuru_durumu", {
                    "durum": "bilgi",
                    "mesaj": "Metin seslendiriliyor...",
                    "chat_id": chat_id
                })

            media_manager.stop_all_media()
            await asyncio.sleep(1.0)
            
            # İptal kontrolü - TTS çalma öncesi
            if media_manager.is_cancelled():
                logging.info("🔴 TTS çalma öncesi iptal edildi")
                raise Exception("İşlem kullanıcı tarafından iptal edildi")
            
            tts_result = media_manager.play_media(tts_media_name)
            
            if not tts_result:
                raise Exception("Metin sesi çalınamadı")
            
            # TTS sesi boyunca iptal kontrolü
            tts_start = time.time()
            while (time.time() - tts_start) < (text_duration + 0.5):  # +2 saniye tolerans
                if media_manager.is_cancelled():
                    logging.info("🔴 TTS sesi sırasında iptal edildi")
                    media_manager.stop_all_media()
                    raise Exception("İşlem kullanıcı tarafından iptal edildi")
                await asyncio.sleep(0.1)
            

            media_manager.stop_all_media()
            await asyncio.sleep(0.5)
            
            # İptal kontrolü - Tekrar öncesi
            if media_manager.is_cancelled():
                logging.info("🔴 Tekrar anonsu öncesi iptal edildi")
                raise Exception("İşlem kullanıcı tarafından iptal edildi")
            
            tekrar_result = media_manager.play_media('tekrar')
            if not tekrar_result:
                raise Exception("Tekrar anonsu çalınamadı")
            
            # Tekrar anonsu boyunca iptal kontrolü
            current_model = ayar_getir("tts_model", "male")
            _normalize = {"erkek-fahrettin": "male", "kadin(yakinda)": "female",
                          "erkek": "male", "kadin": "female"}
            normalized_model = _normalize.get(current_model.lower(), current_model.lower())
            
            tekrar_file = "tekrar1.wav" if normalized_model == "male" else "tekrar2.wav"
            tekrar_path = os.path.join(MEDIA_DIR, tekrar_file)
            if not os.path.exists(tekrar_path):
                tekrar_path = os.path.join(MEDIA_DIR, "tekrar.wav")
                
            tekrar_duration = get_duration(tekrar_path)
            logging.info(f"Tekrar anonsu dosyası: {os.path.basename(tekrar_path)}, Süresi: {tekrar_duration}s")
            
            tekrar_start = time.time()
            while (time.time() - tekrar_start) < (tekrar_duration + 0.5):
                if media_manager.is_cancelled():
                    logging.info("🔴 Tekrar anonsu sırasında iptal edildi")
                    media_manager.stop_all_media()
                    raise Exception("İşlem kullanıcı tarafından iptal edildi")
                await asyncio.sleep(0.1)
            
            media_manager.stop_all_media()
            await asyncio.sleep(0.5)
            
            # İptal kontrolü - TTS tekrar öncesi
            if media_manager.is_cancelled():
                logging.info("🔴 TTS tekrar öncesi iptal edildi")
                raise Exception("İşlem kullanıcı tarafından iptal edildi")
            
            tts_result2 = media_manager.play_media(tts_media_name)
            if not tts_result2:
                raise Exception("Metin tekrar sesi çalınamadı")
            
            # TTS tekrarı boyunca iptal kontrolü
            tts2_start = time.time()
            while (time.time() - tts2_start) < (text_duration + 0.5):
                if media_manager.is_cancelled():
                    logging.info("🔴 TTS tekrarı sırasında iptal edildi")
                    media_manager.stop_all_media()
                    raise Exception("İşlem kullanıcı tarafından iptal edildi")
                await asyncio.sleep(0.1)

            self._update_status_with_style("✅ Seslendirme tamamlandı", "normal")

        except Exception as exc:
            if "iptal" in str(exc).lower():
                logging.info("🔴 Seslendirme iptal edildi")
                self._update_status_with_style("⏹ Seslendirme iptal edildi", "warning")
                
                # Butonları hemen aktif yap
                self.root.after(0, lambda: self._update_control_buttons_state(True))
                self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
                
                # Telegram'a iptal bildirimi gönder
                if chat_id:
                    ee.emit("telegram_duyuru_durumu", {
                        "durum": "uyari",
                        "mesaj": "Seslendirme iptal edildi",
                        "chat_id": chat_id
                    })
            else:
                # Diğer hatalar
                logging.error(f"Seslendirme hatası: {str(exc)}", exc_info=True)
                self._update_status_with_style(f"❌ Seslendirme hatası: {str(exc)}", "error")
                ee.emit("play_error", f"Seslendirme hatası: {str(exc)}")
                
                # Telegram'a hata bildirimi gönder
                if chat_id:
                    ee.emit("telegram_duyuru_durumu", {
                        "durum": "hata",
                        "mesaj": f"Seslendirme hatası: {str(exc)}",
                        "chat_id": chat_id
                    })
        finally:
            # Butonları MUTLAKA aktif yap
            media_manager.set_busy_status(False, "")
            media_manager.reset_cancellation()
            
            # GUI butonlarını güncelle
            self.root.after(0, lambda: self._update_control_buttons_state(True))
            self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
            
            # Progress bar'ı temizle
            if hasattr(self, 'progress'):
                self.root.after(0, self.progress.stop)
                self.root.after(0, self.progress.destroy)
            
            # MediaManager üzerinden temizlik
            media_manager.stop_all_media()
            await asyncio.sleep(0.5)
            
            # Geçici TTS player'ını temizle
            if tts_media_name in media_manager.players:
                try:
                    player_data = media_manager.players[tts_media_name]
                    if player_data.get('player'):
                        try:
                            player_data['player'].stop()
                            player_data['player'].release()
                        except:
                            pass
                    del media_manager.players[tts_media_name]
                except:
                    pass
            
            # Geçici dosyayı sil
            if tmpfile and os.path.exists(tmpfile):
                try:
                    os.remove(tmpfile)
                    logging.debug(f"Geçici dosya silindi: {tmpfile}")
                except Exception as e:
                    logging.error(f"Geçici dosya silinemedi: {e}")



    async def _wait_for_player(self, player, timeout):
        """Dinamik bekleme: VLC state ile kontrol et"""
        if not player:
            logging.warning("Player None, bekleme atlanıyor")
            return
        
        await asyncio.sleep(1.2)  # Artırıldı: 1.0 -> 1.2 (MP3 yükleme)
        
        start_time = time.time()
        while (time.time() - start_time < timeout):
            if player:
                state = player.get_state()
                if state in [vlc.State.Ended, vlc.State.Stopped, vlc.State.Error]:
                    logging.info(f"⏹ Player bitti (state: {state})")
                    break
                elif not player.is_playing():
                    logging.debug(f"is_playing() False, state: {state}")
                    await asyncio.sleep(0.1)
                else:
                    await asyncio.sleep(0.05)
            else:
                break
        
        await asyncio.sleep(0.5)  # Ek tampon artırıldı
        logging.debug(f"Player bekleme tamamlandı (süre: {time.time() - start_time:.1f}s, state: {player.get_state() if player else 'None'})")


    def _reset_media_system(self):
        """Medya sistemini resetle (acil durum)"""
        try:
            logging.warning("🔄 Medya sistemi resetleniyor...")
            
            from config.settings import media_manager
            
            # MediaManager'ı resetle
            media_manager.stop_all_media()
            
            # Durumları manuel sıfırla
            media_manager.is_playing = False
            media_manager.currently_playing = None
            media_manager.is_busy = False
            media_manager.busy_message = ""
            
            # GUI durumunu güncelle
            self._update_control_buttons_state(True)
            self.btn_seslendir.configure(state='normal')
            self._update_status_with_style("✅ Sistem resetlendi", "normal")
            
            logging.info("✅ Medya sistemi başarıyla resetlendi")
            
        except Exception as e:
            logging.error(f"❌ Sistem reset hatası: {str(e)}")
            # Son çare: uygulamayı yeniden başlatma önerisi
            self._update_status_with_style("❌ Sistem hatası! Lütfen yeniden başlatın", "error")


    def seslendir_metin(self, chat_id=None):
        """
        Metni seslendir - GÜNCELLENDİ
        :param chat_id: Telegram chat ID (opsiyonel)
        """
        # Meşguliyet kontrolü ekle
        from config.settings import media_manager
        if media_manager.is_media_busy():
            busy_message = media_manager.get_busy_message()
            status_msg = f"⚠️ Şu anda {busy_message} çalıyor. Lütfen bekleyin..."
            self._update_status_with_style(status_msg, "warning")
            
            # Telegram'a bildirim gönder
            if chat_id:
                ee.emit("telegram_duyuru_durumu", {
                    "durum": "uyari",
                    "mesaj": status_msg,
                    "chat_id": chat_id
                })
            return

        # YENİ: Seslendirme başladığını bildir ve butonları pasif yap
        ee.emit("tts_started", {"message": "Metin seslendirme başlatılıyor"})
        self._update_control_buttons_state(False)  # Butonları pasif yap
        self.btn_seslendir.configure(state='disabled')
        
        metin = self.text_input.get("1.0", tk.END).strip()
        if not metin:
            status_msg = "Seslendirilecek metin boş!"
            logging.warning(status_msg)
            self._update_status_with_style(status_msg, "warning")
            
            # Butonları tekrar aktif yap
            self._update_control_buttons_state(True)
            self.btn_seslendir.configure(state='normal')
            
            # Telegram'a bildirim gönder
            if chat_id:
                ee.emit("telegram_duyuru_durumu", {
                    "durum": "uyari", 
                    "mesaj": status_msg,
                    "chat_id": chat_id
                })
            return

        # İlerleme çubuğunu göster
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        self.progress.pack(pady=10)
        self.progress.start()

        # Başlangıç bildirimi
        status_msg = "🔄 Seslendirme hazırlıkları yapılıyor..."
        self._update_status_with_style(status_msg, "normal")
        
        # Telegram'a başlama bildirimi gönder
        if chat_id:
            ee.emit("telegram_duyuru_durumu", {
                "durum": "bilgi",
                "mesaj": status_msg,
                "chat_id": chat_id
            })

        # Onay sormadan direkt seslendirmeyi başlat
        threading.Thread(
            target=self._seslendir_metin_thread,
            args=(metin, chat_id),
            daemon=True
        ).start()



    def _seslendir_metin_thread(self, metin, chat_id=None):
        try:
            future = asyncio.run_coroutine_threadsafe(self.seslendir_metin_async(metin, chat_id), self.async_loop)
            future.result()
        except Exception as exc:
            logging.error(f"Seslendirme thread hatası: {str(exc)}", exc_info=True)
            ee.emit("play_error", f"Seslendirme hatası: {str(exc)}")
            
            # Telegram'a hata bildirimi gönder
            if chat_id:
                ee.emit("telegram_duyuru_durumu", {
                    "durum": "hata",
                    "mesaj": f"Seslendirme hatası: {str(exc)}",
                    "chat_id": chat_id
                })
        finally:
            # Butonu tekrar aktif yap
            self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
            
            # İlerleme çubuğunu kaldır
            if hasattr(self, 'progress'):
                self.root.after(0, self.progress.stop)
                self.root.after(0, self.progress.destroy)


    def _reset_media_system(self):
        """Medya sistemini resetle (acil durum)"""
        try:
            logging.warning("🔄 Medya sistemi resetleniyor...")
            
            from config.settings import media_manager
            
            # MediaManager'ı resetle
            media_manager.stop_all_media()
            
            # Durumları manuel sıfırla
            media_manager.is_playing = False
            media_manager.currently_playing = None
            media_manager.is_busy = False
            media_manager.busy_message = ""
            
            # GUI durumunu güncelle
            self._update_control_buttons_state(True)
            self.btn_seslendir.configure(state='normal')
            self._update_status_with_style("✅ Sistem resetlendi", "normal")
            
            logging.info("✅ Medya sistemi başarıyla resetlendi")
            
        except Exception as e:
            logging.error(f"❌ Sistem reset hatası: {str(e)}")
            # Son çare: uygulamayı yeniden başlatma önerisi
            self._update_status_with_style("❌ Sistem hatası! Lütfen yeniden başlatın", "error")



    def shutdown_pc(self):
        if messagebox.askyesno("Onay", "Bilgisayarı kapatmak istediğinize emin misiniz?"):
            os.system("shutdown /s /t 6" if os.name == 'nt' else "sudo shutdown -h now")



    def zil_sesi_degistir(self):
        selected_tur = simpledialog.askstring(
            "Ses Türü Seçin", 
            "Değiştirmek istediğiniz ses türünü girin:\n"
            "1. Öğrenci Zili (zil.mp3)\n"
            "2. Öğretmen Zili (ogretmen_zil.mp3)\n" 
            "3. Teneffüs Zili (teneffus_zil.mp3)\n"
            "Lütfen numara girin (1-3):",
            parent=self.root
        )
        
        tur_map = {
            "1": ("ogrenci", "zil.mp3"),
            "2": ("ogretmen", "ogretmen_zil.mp3"),
            "3": ("teneffus", "teneffus_zil.mp3"), 
            "4": ("konusmaci", "speaker.wav")
        }
        
        if selected_tur not in tur_map:
            messagebox.showerror("İptal", "Komut iptal edildi")
            return
        
        tur_bilgisi, dosya_adi = tur_map[selected_tur]
        
        # WAV dosyaları için filetypes ayarı
        if dosya_adi.endswith('.wav'):
            filetypes = [("WAV Dosyaları", "*.wav")]
        else:
            filetypes = [("MP3 Dosyaları", "*.mp3")]
        
        file_path = filedialog.askopenfilename(
            title=f"{tur_bilgisi.capitalize()} Sesini Seçin",
            filetypes=filetypes
        )
        if not file_path:
            return
        
        try:
            hedef_yol = media_manager.MEDIA_DIR / dosya_adi
            
            # Yedek al
            backup_exists = hedef_yol.exists()
            if backup_exists:
                overwrite = messagebox.askyesno(
                    "Uyarı",
                    f"{tur_bilgisi.capitalize()} sesi değiştirilecek, emin misiniz?\n\n"
                    "NOT: Anons ses modeli değişirse 'tekrar.wav' otomatik güncellenecektir."  # Güncellendi
                )
                if not overwrite:
                    return
                
                # Yedek oluştur
                backup_path = hedef_yol.with_suffix('.bak')
                shutil.copy2(hedef_yol, backup_path)
            
            shutil.copy(file_path, hedef_yol)
            
            if tur_bilgisi == "konusmaci":
                # Progress bar göster
                self.progress = ttk.Progressbar(self.root, mode='indeterminate')
                self.progress.pack(pady=10)
                self.progress.start()
                
                self._update_status_with_style("🔄 Anons ses modeli güncelleniyor...", "warning")
                self.root.update()  # GUI'yi güncelle
                
                # Async olarak yeniden yükle
                def reload_async():
                    try:
                        from utils.tts_manager import tts_manager
                        success = tts_manager.reload_speaker()
                        
                        # GUI thread'inde sonucu işle
                        self.root.after(0, lambda: self._handle_reload_result(success))
                        
                    except Exception as e:
                        self.root.after(0, lambda: self._handle_reload_result(False, str(e)))
                
                # Arka planda çalıştır
                threading.Thread(target=reload_async, daemon=True).start()
            else:
                # Normal zil sesleri için
                messagebox.showinfo("Başarılı", f"{tur_bilgisi.capitalize()} sesi güncellendi!")
                media_manager.players[tur_bilgisi] = vlc.MediaPlayer(str(hedef_yol))
                media_manager._set_volumes()
                
            logging.info(f"Ses dosyası güncellendi: {tur_bilgisi} -> {hedef_yol}")
            
        except Exception as exc:
            logging.error(f"Ses değiştirme hatası: {str(exc)}")
            messagebox.showerror("Hata", f"Dosya işlenirken hata oluştu: {str(exc)}")
            
            # Hata durumunda yedeği geri yükle
            if backup_exists and 'backup_path' in locals() and backup_path.exists():
                try:
                    shutil.copy2(backup_path, hedef_yol)
                    logging.info("Yedek geri yüklendi")
                except Exception as backup_error:
                    logging.error(f"Yedek geri yükleme hatası: {backup_error}")
                    

    def _handle_reload_result(self, success, error_msg=""):
        """Reload işlemi sonucunu işle"""
        # Progress bar'ı kaldır
        if hasattr(self, 'progress'):
            self.progress.stop()
            self.progress.destroy()
        
        if success:
            self._update_status_with_style("✅ Anons ses modeli güncellendi", "normal")
        else:
            self._update_status_with_style(f"❌ Güncelleme hatası: {error_msg}", "error")
            messagebox.showerror("Hata", f"Anons ses modeli güncellenemedi:\n{error_msg}")

            
    def setup_event_listeners(self):
        self.internet_warning_shown = False

        def update_list():
            self.listeyi_guncelle()
            
        
        ee.on("volume_changed", self.update_volume_ui)
        ee.on("bells_enabled_changed", self._on_bells_enabled_changed)

        def handle_veri_degisti():
            # GUI listesini hemen güncelle
            self.root.after(0, self.listeyi_guncelle)
            logging.info("GUI listesi güncellendi (veri_degisti event)")
            
        ee.on("veri_degisti", lambda *args: self.root.after(0, update_list))

        def update_internet_status(is_connected):
            logging.info(f"İnternet durumu güncellendi: {is_connected}")
            BOT_TOKEN = ayar_getir("telegram_api_key")
            
            if not BOT_TOKEN or BOT_TOKEN == "Api key giriniz":
                self.btn_telegram.configure(state='normal')
                # Seslendir butonunu her zaman aktif tut (internetten bağımsız)
                self.btn_seslendir.configure(state='normal')
                self._update_status_with_style("⚠️ Telegram API anahtarı eksik!", "warning")
                return

            if is_connected:
                status_text = "🌐 Bağlantı sağlandı"
                bg_color = "#2ecc71"  # Yeşil
                self.btn_telegram.configure(state='normal')
                # Seslendir butonunu her zaman aktif tut (internetten bağımsız)
                self.btn_seslendir.configure(state='normal')
                self.internet_warning_shown = False
            else:
                status_text = "❌ İnternet bağlantısı kesildi"
                bg_color = "#e74c3c"  # Kırmızı
                self.btn_telegram.configure(state='disabled')
                # Seslendir butonunu her zaman aktif tut (internetten bağımsız)
                self.btn_seslendir.configure(state='normal')
                
                # BİLDİRİM PENCERESİNİ KALDIRDIK - sadece log
                if not self.internet_warning_shown:
                    logging.warning("İnternet bağlantısı kesildi, Telegram bot'u durduruldu.")
                    self.internet_warning_shown = True
            
            self._update_status_with_style(status_text, "connected" if is_connected else "disconnected")

        # Event listener'ı ekle (bildirim olmadan)
        ee.on("internet_status_changed", lambda is_connected: self.root.after(0, lambda: update_internet_status(is_connected)))

        def handle_invalid_token():
            self._update_status("❌ Geçersiz Telegram API anahtarı!")
            self.show_invalid_token_message()
            self.btn_telegram.configure(state='normal')
            self.btn_seslendir.configure(state='disabled')

        ee.on("invalid_token", lambda: self.root.after(0, handle_invalid_token))

        def check_token_on_settings_change():
            BOT_TOKEN = ayar_getir("telegram_api_key")
            if (not BOT_TOKEN or BOT_TOKEN == "Api key giriniz") and not self.invalid_token_shown:
                self.show_invalid_token_message()
        
        ee.on("settings_changed", check_token_on_settings_change)

        def handle_bot_started():
            BOT_TOKEN = ayar_getir("telegram_api_key")
            if BOT_TOKEN and BOT_TOKEN != "Api key giriniz":
                self.btn_telegram.configure(state='normal')
                self.btn_seslendir.configure(state='normal')
                self._update_status("✅ Telegram botu çalışıyor")
            else:
                self.btn_telegram.configure(state='normal')
                self.btn_seslendir.configure(state='disabled')
                self._update_status("⚠️ Telegram API anahtarı eksik!")

        ee.on("bot_started", lambda: self.root.after(0, handle_bot_started))


        def handle_tts_ready():
            logging.info("✅ TTS motoru hazır")
            self._update_status_with_style("✅ TTS motoru hazır", "normal")
        ee.on("tts_ready")
        

        def handle_tts_error(error_msg):
            logging.error(f"❌ TTS hatası: {error_msg}")
            self._update_status_with_style("❌ TTS yüklenemedi", "error")
            self.btn_seslendir.configure(state='disabled')
            messagebox.showwarning(
                "TTS Hatası",
                f"Seslendirme servisi yüklenemedi: {error_msg}\n"
                "Seslendirme özelliği devre dışı bırakıldı. Uygulamayı yeniden başlatmayı deneyin."
            )
        ee.on("tts_error")
        

        def handle_tts_progress(data):
            stage = data.get("stage", "")
            message = data.get("message", "")
            
            if stage == "processing":
                self._update_status_with_style(message, "warning")
            elif stage == "completed":
                self._update_status_with_style(message, "normal")
            elif stage == "error":
                self._update_status_with_style(message, "error")
        
        ee.on("tts_progress", lambda data: self.root.after(0, lambda: handle_tts_progress(data)))


        def restart_application():
            if messagebox.askyesno("Yeniden Başlat", "İnternet bağlantısı sağlandı, uygulama yeniden başlatılsın mı?"):
                self.root.destroy()
                python = sys.executable
                subprocess.Popen([python, sys.argv[0]])
                sys.exit()

        ee.on("restart_application", lambda: self.root.after(0, restart_application))
        ee.on("play_error", lambda msg: self.root.after(0, lambda: self.show_play_error(msg)))


        def handle_media_busy_change(data):
            """Medya meşguliyet durumu değiştiğinde çağrılır - GÜNCELLENDİ"""
            is_busy = data.get('is_busy', False)
            message = data.get('message', '')
            self.root.after(0, lambda: self._handle_media_busy_status(is_busy, message))
        
        def _handle_media_busy_status(self, is_busy, message=""):
            """Medya meşguliyet durumuna göre GUI'yi günceller - GÜNCELLENDİ"""
            if is_busy:
                # Meşgul durumda: ses çalma butonlarını pasif yap, durdur butonu AKTİF kalsın
                play_buttons_state = False
                self._update_status_with_style(f"🔊 {message} çalınıyor...", "warning")
            else:
                # Boş durumda: ses çalma butonlarını aktif yap, durdur butonu yine AKTİF kalsın
                play_buttons_state = True
                self._update_status_with_style("✅ Sistem hazır", "normal")
            
            # Ses çalma butonlarının durumunu güncelle (durdur butonu her zaman aktif)
            self._update_control_buttons_state(play_buttons_state)
            
            # Seslendir butonunu ayrıca kontrol et
            if is_busy:
                self.btn_seslendir.configure(state='disabled')
            else:
                self.btn_seslendir.configure(state='normal')

        def handle_media_ended(event_data):
            """Medya bittiğinde butonları aktif yap - GÜNCELLENDİ"""
            # Ses çalma butonlarını aktif yap, durdur butonu zaten aktif
            self._update_control_buttons_state(True)
            self.btn_seslendir.configure(state='normal')
            self._update_status_with_style("✅ Sistem hazır", "normal")
            logging.debug("Medya bitti, butonlar aktif yapıldı")

        def handle_media_cancelled():
            """Medya iptal edildiğinde çağrılır - GÜNCELLENDİ"""
            logging.info("🔴 Medya iptal event'i alındı")
            # Butonları hemen aktif yap
            self._update_control_buttons_state(True)
            self.btn_seslendir.configure(state='normal')
            self._update_status_with_style("✅ Sistem hazır", "normal")

        # Event listener'ları ekle
        ee.on("media_busy_status", lambda data: self.root.after(0, lambda: handle_media_busy_change(data)))
        ee.on("media_ended", lambda event_data: self.root.after(0, handle_media_ended))
        ee.on("media_cancelled", lambda: self.root.after(0, handle_media_cancelled))

        def handle_tts_started(data):
            """Seslendirme başladığında çağrılır"""
            self.root.after(0, lambda: self._handle_media_busy_status(True, "Metin Seslendirme"))
        
        # Event listener'ları ekle
        ee.on("tts_started", lambda data: self.root.after(0, lambda: handle_tts_started(data)))  # YENİ


        def handle_telegram_media_started(data):
            """Telegram'dan medya başladığında GUI'yi güncelle"""
            media_type = data.get('media_type', '')
            display_name = data.get('display_name', '')
            source = data.get('source', 'telegram')
            
            # Butonları pasif yap
            self.root.after(0, lambda: self._update_control_buttons_state(False))
            
            # Durum çubuğunu güncelle
            status_text = f"📱 Telegram: {display_name} çalınıyor..."
            self.root.after(0, lambda: self._update_status_with_style(status_text, "normal"))
            
            logging.info(f"Telegram medya başladı: {media_type}")

        # YENİ: Gelişmiş stop_all_media event handler
        def handle_stop_all_media_advanced(data):
            """Tüm medyaları durdur - GELİŞMİŞ VERSİYON"""
            try:
                source = data.get('source', 'unknown')
                chat_id = data.get('chat_id', '')
                timestamp = data.get('timestamp', 0)
                
                logging.info(f"🔴 Durdurma isteği geldi: kaynak={source}, chat_id={chat_id}")
                
                # Çakışma önleme
                if hasattr(self, '_stop_processing') and self._stop_processing:
                    logging.debug("⏭️ Durdurma işlemi zaten devam ediyor, atlandı")
                    return
                    
                self._stop_processing = True
                
                # MediaManager üzerinden durdur
                from config.settings import media_manager
                media_manager.stop_all_media()
                
                # GUI durumunu GECİKMEDEN güncelle
                self.root.after(0, lambda: self._update_control_buttons_state(True))
                self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
                
                # Kaynağa göre farklı mesaj
                if source == 'telegram':
                    status_text = "✅ Telegram: Tüm sesler durduruldu"
                else:
                    status_text = "✅ Tüm sesler durduruldu"
                    
                self.root.after(0, lambda: self._update_status_with_style(status_text, "normal"))
                
                # GUI'yi hemen güncelle
                self.root.after(0, self.root.update_idletasks)
                
                logging.info(f"✅ {source} kaynaklı durdurma tamamlandı")
                
            except Exception as e:
                logging.error(f"❌ Durdurma event işleme hatası: {str(e)}", exc_info=True)
            finally:
                # İşlem tamamlandığında flag'i sıfırla
                self._stop_processing = False

        # EVENT LİSTENER'LARI EKLE
        ee.on("telegram_media_started", lambda data: self.root.after(0, lambda: handle_telegram_media_started(data)))
        ee.on("stop_all_media", lambda data: self.root.after(0, lambda: handle_stop_all_media_advanced(data)))
            
        # YENİ: MediaManager durum senkronizasyonu
        def handle_media_manager_sync():
            """MediaManager durumunu GUI ile senkronize et"""
            try:
                from config.settings import media_manager
                
                # MediaManager durumunu kontrol et ve GUI'yi güncelle
                if media_manager.is_playing:
                    # Çalıyorsa butonları pasif yap
                    self.root.after(0, lambda: self._update_control_buttons_state(False))
                else:
                    # Durmuşsa butonları aktif yap
                    self.root.after(0, lambda: self._update_control_buttons_state(True))
                    self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
                    
            except Exception as e:
                logging.error(f"Senkronizasyon hatası: {str(e)}")
        
        # EVENT LİSTENER'LARI EKLE
        ee.on("telegram_media_started", lambda data: self.root.after(0, lambda: handle_telegram_media_started(data)))
        ee.on("stop_all_media", lambda data: self.root.after(0, lambda: handle_stop_all_media_advanced(data)))
        
        # 5 saniyede bir senkronizasyon yap
        def start_sync_timer():
            handle_media_manager_sync()
            self.root.after(5000, start_sync_timer)  # Her 5 saniyede bir
        
        start_sync_timer()


        # Yeni Telegram duyuru event listener'ları
        def handle_telegram_duyuru(data):
            """Telegram'dan gelen duyuru metnini işle"""
            try:
                metin = data.get('metin', '')
                user_info = data.get('user', 'Telegram Kullanıcısı')
                chat_id = data.get('chat_id', '')
                
                if metin:
                    # Metni GUI text input'una yaz
                    self.text_input.delete("1.0", tk.END)
                    self.text_input.insert("1.0", metin)
                    
                    # Durum çubuğunu güncelle
                    self._update_status_with_style(f"📢 Telegram Duyuru: {user_info}", "normal")
                    
                    # Telegram'a bildirim gönder
                    ee.emit("telegram_duyuru_durumu", {
                        "durum": "bilgi",
                        "mesaj": "Duyuru metni alındı, seslendirme başlatılıyor...",
                        "chat_id": chat_id
                    })
                    
                    # 2 saniye bekle ve otomatik seslendir
                    self.root.after(2000, lambda: self.seslendir_metin(chat_id))
                    
            except Exception as e:
                logging.error(f"Telegram duyuru işleme hatası: {str(e)}")
                
                # Hata durumunda Telegram'a bildir
                if 'chat_id' in data:
                    ee.emit("telegram_duyuru_durumu", {
                        "durum": "hata",
                        "mesaj": f"Duyuru işleme hatası: {str(e)}",
                        "chat_id": data['chat_id']
                    })

        def handle_duyuru_durumu(data):
            """Duyuru durumunu Telegram'a bildir"""
            durum = data.get('durum', '')
            mesaj = data.get('mesaj', '')
            chat_id = data.get('chat_id', '')
            
            if durum and mesaj and chat_id:
                status_type = "normal"
                if durum == "hata":
                    status_type = "error"
                elif durum == "uyari":
                    status_type = "warning"
                elif durum == "bilgi":
                    status_type = "normal"
                    
                self._update_status_with_style(f"📢 {mesaj}", status_type)

        # Event listener'ları ekle
        ee.on("telegram_duyuru_metni", lambda data: self.root.after(0, lambda: handle_telegram_duyuru(data)))
        ee.on("telegram_duyuru_durumu", lambda data: self.root.after(0, lambda: handle_duyuru_durumu(data)))


        def handle_telegram_media_request(data):
            """Telegram'dan gelen medya isteklerini işle"""
            media_type = data.get('media_type')
            source = data.get('source', 'telegram')
            user_info = data.get('user_info', 'Telegram Kullanıcısı')
            
            # GUI üzerinden medyayı çal
            self.root.after(0, lambda: self._play_media_from_telegram(media_type, user_info))
            
        # Son çalışan stop event'i takip etmek için
        self.last_stop_event = None
        self.stop_in_progress = False  # ⚠️ YENİ: Çakışma önleme
        
        def handle_stop_all_media(data):
            """Tüm medyaları durdur - ÇAKIŞMA ÖNLEMELİ"""
            try:
                source = data.get('source', 'unknown')
                timestamp = data.get('timestamp', 0)
                
                # Çakışma önleme
                if self.stop_in_progress:
                    logging.debug("⏭️ Stop işlemi zaten devam ediyor, atlandı")
                    return
                    
                # Aynı event'i tekrar işleme (duplicate prevention)
                if self.last_stop_event and (timestamp - self.last_stop_event) < 1.0:
                    logging.debug("⏭️ Yakın zamandaki stop event'i atlandı")
                    return
                    
                self.stop_in_progress = True
                self.last_stop_event = timestamp
                
                logging.info(f"⏹️ Tüm medyalar durduruluyor (kaynak: {source})")
                
                # ⚠️ SADECE BIR KEZ MediaManager'ı çağır
                from config.settings import media_manager
                media_manager.stop_all_media()
                
                # GUI durumunu GECİKMEDEN güncelle
                self.root.after(0, lambda: self._update_control_buttons_state(True))
                self.root.after(0, lambda: self.btn_seslendir.configure(state='normal'))
                self.root.after(0, lambda: self._update_status_with_style("✅ Tüm sesler durduruldu", "normal"))
                
                # GUI'yi hemen güncelle
                self.root.after(0, self.root.update_idletasks)
                
                logging.info(f"✅ {source} kaynaklı durdurma tamamlandı")
                
            except Exception as e:
                logging.error(f"❌ Stop event işleme hatası: {str(e)}", exc_info=True)
            finally:
                # İşlem tamamlandığında flag'i sıfırla
                self.stop_in_progress = False
        
        # Event listener'ı ekle
        ee.on("stop_all_media", lambda data: self.root.after(0, lambda: handle_stop_all_media(data)))
        
        def handle_media_status_changed(data):
            """Medya durumu değişikliklerini işle"""
            is_playing = data.get('playing', False)
            media_type = data.get('media_type', '')
            display_name = data.get('display_name', '')
            source = data.get('source', 'gui')
            
            if is_playing:
                # Medya çalıyor - butonları pasif yap
                self.root.after(0, lambda: self._update_control_buttons_state(False))
                
                source_text = "Telegram" if source == 'telegram' else "GUI"
                status_text = f"▶️ {display_name} çalınıyor ({source_text})"
                self.root.after(0, lambda: self._update_status_with_style(status_text, "normal"))
            else:
                # Medya durdu - butonları aktif yap
                self.root.after(0, lambda: self._update_control_buttons_state(True))
                self.root.after(0, lambda: self._update_status_with_style("✅ Sistem hazır", "normal"))
        
        # Yeni event listener'ları ekle
        ee.on("telegram_media_request", lambda data: self.root.after(0, lambda: handle_telegram_media_request(data)))
        ee.on("stop_all_media", lambda data: self.root.after(0, lambda: handle_stop_all_media(data)))
        ee.on("media_status_changed", lambda data: self.root.after(0, lambda: handle_media_status_changed(data)))
        
        # Scheduler'dan gelen çalma isteklerini dinle (GÜNCELLENDİ)
        def handle_scheduler_request(command):
            logging.info(f"🔔 Scheduler isteği GUI'ye ulaştı: {command}")
            self.root.after(0, lambda: self._handle_control(command))
        ee.on("scheduler_play_request", handle_scheduler_request)


        def handle_tts_speaker_reloaded(data):
            """TTS speaker reload event'ini işle - GELİŞMİŞ"""
            success = data.get("success", False)
            error = data.get("error", "")
            requires_restart = data.get("requires_restart", False)
            
            if success:
                message = data.get("message", "✅ Anons ses modeli güncellendi!")
                
                # Başarı mesajını göster
                messagebox.showinfo(
                    "Başarılı",
                    f"{message}\n\n"
                    f"'tekrar.wav' dosyası yeni sesle otomatik olarak güncellendi."
                )
                self._update_status_with_style("✅ Anons ses modeli güncellendi", "normal")
                
            else:
                # Hata mesajını detaylı göster
                error_title = "Yeniden Başlat Gerekli" if requires_restart else "Hata"
                
                if requires_restart:
                    error_msg = f"❌ {error}\n\nUygulamayı yeniden başlatmanız gerekiyor."
                    result = messagebox.askyesno(
                        "Yeniden Başlat Gerekli",
                        f"{error_msg}\n\nŞimdi yeniden başlatılsın mı?"
                    )
                    
                    if result:
                        # Yeniden başlat
                        from utils.helpers import restart_application
                        restart_application()
                else:
                    messagebox.showerror(
                        "Hata",
                        f"❌ {error}\n\nLütfen logları kontrol edin ve tekrar deneyin."
                    )
                    self._update_status_with_style("❌ Anons ses modeli güncellenemedi", "error")

        ee.on("tts_speaker_reloaded", lambda data: self.root.after(0, lambda: handle_tts_speaker_reloaded(data)))
            

    def _play_media_from_telegram(self, media_type, user_info):
        """Telegram'dan gelen medya isteğini GUI üzerinden çal"""
        try:
            from config.settings import media_manager
            
            # Meşguliyet kontrolü
            if media_manager.is_media_busy():
                busy_message = media_manager.get_busy_message()
                status_msg = f"⚠️ Şu anda {busy_message} çalıyor. Telegram isteği bekletiliyor..."
                self._update_status_with_style(status_msg, "warning")
                return
            
            # GUI üzerinden medyayı çal
            result = media_manager.play_media(media_type, source='telegram')
            
            if result:
                status_msg = f"📱 {user_info} → {media_type.capitalize()}"
                self._update_status_with_style(status_msg, "normal")
            else:
                status_msg = f"❌ {media_type} çalınamadı"
                self._update_status_with_style(status_msg, "error")
                
        except Exception as e:
            logging.error(f"Telegram medya çalma hatası: {str(e)}")
            self._update_status_with_style(f"❌ Telegram isteği hatası: {str(e)}", "error")


    def show_play_error(self, message):
        messagebox.showwarning("Uyarı", message)
        self._update_status_with_style(f"⚠️ {message}", "error")

    def listeyi_guncelle(self, *args):
        """Grid'i DB'deki mevcut zil saatleriyle yeniler."""
        try:
            bells = listele_zil()
            by_type = {t: sorted(s for _, s, tp, _ in bells if tp == t)
                       for t in ("ogrenci", "ogretmen", "teneffus")}
            for row, row_entries in enumerate(self.grid_entries):
                for tur, entry in row_entries.items():
                    entry.delete(0, tk.END)
                    lst = by_type.get(tur, [])
                    if row < len(lst):
                        entry.insert(0, lst[row])
            self.root.update_idletasks()
            self._update_status_with_style("✅ Zil tablosu güncellendi", "normal")
        except Exception as e:
            logging.error(f"listeyi_guncelle hatası: {e}", exc_info=True)
            self._update_status_with_style("⚠️ Zil tablosu güncellenemedi", "warning")

    def _save_grid(self):
        """Grid'deki saatleri doğrulayıp DB'ye kaydeder."""
        SAAT_RE = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')
        TURLER = ["ogrenci", "ogretmen", "teneffus"]
        errors, valid, seen = [], [], set()

        for row_idx, row_entries in enumerate(self.grid_entries):
            for tur in TURLER:
                saat = row_entries[tur].get().strip()
                if not saat:
                    continue
                if not SAAT_RE.match(saat):
                    errors.append(f"{row_idx+1}. satır {tur}: geçersiz '{saat}'")
                    continue
                key = (saat, tur)
                if key in seen:
                    errors.append(f"Tekrar giriş: {saat} ({tur})")
                    continue
                seen.add(key)
                valid.append((saat, tur, f"{tur}_{saat.replace(':', '')}"))

        if errors:
            messagebox.showerror("Format Hatası", "\n".join(errors[:8]))
            return

        try:
            from utils.database import sil_tum_zil_saatleri
            sil_tum_zil_saatleri()
            basarili = sum(1 for s, t, j in valid if ekle_zil(s, t, j))
            from utils.scheduler import refresh_scheduler
            refresh_scheduler()
            logging.info(f"Grid kaydedildi: {basarili}/{len(valid)} saat")
            self._update_status_with_style(f"✅ {basarili} zil saati kaydedildi", "normal")
            messagebox.showinfo(
                "Kaydedildi",
                f"✅ {basarili} zil saati başarıyla kaydedildi\n"
                f"(Öğrenci / Öğretmen / Teneffüs dahil)"
            )
        except Exception as exc:
            logging.error(f"Grid kaydetme hatası: {exc}", exc_info=True)
            messagebox.showerror("Hata", f"Kaydetme hatası: {exc}")

    def update_volume_ui(self, volume):
        self.volume_scale.set(volume)
        self.volume_percent.config(text=f"%{int(volume)}")
        self.volume_icon.config(text="🔊" if volume > 0 else "🔇")
        self.last_volume_value = volume
        logging.debug(f"Ses seviyesi UI güncellendi: {volume}%")

    def zil_ekle(self):
        pass  # Grid sistemi ile değiştirildi — _save_grid kullanın
        
    def zil_toplu_ekle_yeni(self):
        pass  # Grid sistemi ile değiştirildi — _save_grid kullanın

    def sil_tum_zil_saatleri(self):
        logging.debug("sil_tum_zil_saatleri çağrıldı")
        try:
            if messagebox.askyesno("Onay", "Tüm zil saatlerini silmek istediğinize emin misiniz?"):
                from utils.database import sil_tum_zil_saatleri
                if sil_tum_zil_saatleri():
                    logging.info("Tüm zil saatleri silindi")
                    self.listeyi_guncelle()  # Doğrudan çağır
                    self.root.update_idletasks()  # GUI'yi zorla yenile
                    messagebox.showinfo("Başarılı", "Tüm zil saatleri silindi!")
                    self._update_status_with_style("✅ Tüm zil saatleri silindi", "normal")
                else:
                    logging.error("Tüm zil saatleri silme başarısız")
                    messagebox.showerror("Hata", "Zil saatleri silinemedi!")
                    self._update_status_with_style("⚠️ Zil saatleri silinemedi", "warning")
        except Exception as e:
            logging.error(f"sil_tum_zil_saatleri hatası: {str(e)}", exc_info=True)
            messagebox.showerror("Hata", f"Zil saatleri silinirken bir hata oluştu: {str(e)}")
            self._update_status("⚠️ Zil saatleri silinemedi")

    def confirm_action(self, action):
        return messagebox.askyesno("Onay", f"{action} işlemini gerçekleştirmek istediğinize emin misiniz?")

    def show_context_menu(self, event, tree):
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _get_zil_id(self, saat, tur):
        try:
            from utils.database import DB_PATH  # DB_PATH'ı import edin
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT id FROM zil_saatleri WHERE saat=? AND tur=?",
                    (saat, tur)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as exc:
            logging.error(f"Zil ID alınamadı: {str(exc)}")
            messagebox.showerror("Veritabanı Hatası", f"Zil ID alınamadı: {str(exc)}")
            return None
    
    def toggle_bells(self):
        """Zilleri açıp kapatır ve buton durumunu günceller"""
        try:
            new_state = not self.bells_enabled_var.get()
            if set_bells_enabled(new_state):
                self.bells_enabled_var.set(new_state)
                self._update_toggle_button()
                self._update_status_with_style(f"🔔 Ziller {'aktif' if new_state else 'pasif'} yapıldı", "normal")
                logging.info(f"GUI: Ziller {'aktif' if new_state else 'pasif'} yapıldı")
            else:
                messagebox.showerror("Hata", "Zil durumu değiştirilemedi!")
        except Exception as e:
            logging.error(f"Zil durumu değiştirme hatası: {str(e)}", exc_info=True)
            messagebox.showerror("Hata", f"Zil durumu değiştirilemedi: {str(e)}")

    def _update_toggle_button(self):
        """Zil aç/kapa butonunun metnini ve stilini günceller"""
        enabled = self.bells_enabled_var.get()
        self.btn_toggle_bells.config(
            text="🔕ZİLLERİ KAPAT" if enabled else "🔔ZİLLERİ AÇ",
            style="Warning.TButton" if enabled else "Success.TButton"
        )


    def _on_bells_enabled_changed(self, enabled):
        """EventEmitter üzerinden gelen zil durumu değişikliklerini işler"""
        self.bells_enabled_var.set(enabled)
        self._update_toggle_button()
        self._update_status(f"🔔 Ziller {'aktif' if enabled else 'pasif'} yapıldı")


    def _update_control_buttons_state(self, enabled=True):
        """Ses kontrol butonlarının durumunu günceller - GÜÇLENDİRİLMİŞ"""
        # --- BU KISMI EKLE ---
        if not hasattr(self, 'control_frame') or self.control_frame is None:
            return
        # ---------------------
        try:
            # Tüm butonları bul
            all_buttons = []
            for widget in self.control_frame.winfo_children():
                if isinstance(widget, ttk.Button):
                    all_buttons.append(widget)
            
            # Butonları kategorilere ayır
            play_buttons = []  # Ses çalma butonları
            stop_button = None  # Sesleri durdur butonu
            
            for btn in all_buttons:
                text = btn.cget("text")
                if "DURDUR" in text or "DURDUR" in text:
                    stop_button = btn
                else:
                    # Sadece ses çalma butonlarını ekle
                    if any(keyword in text for keyword in ["ZİLİ", "MARŞI", "DURUŞU", "SİREN", "EZAN", "SELA", "OKU"]):
                        play_buttons.append(btn)
            
            # Durumları güncelle
            play_state = 'normal' if enabled else 'disabled'
            
            # SESLERİ DURDUR butonu HER ZAMAN AKTİF OLSUN
            stop_state = 'normal'
            
            for btn in play_buttons:
                try:
                    btn.configure(state=play_state)
                except Exception as e:
                    logging.warning(f"Buton durum güncelleme uyarısı: {str(e)}")
            
            if stop_button:
                try:
                    stop_button.configure(state=stop_state)
                except Exception as e:
                    logging.warning(f"Durdur butonu güncelleme uyarısı: {str(e)}")
                    
            logging.debug(f"🔧 Buton durumları: Oynatma='{play_state}', Durdur='{stop_state}'")
            
            # GUI'yi hemen güncelle
            self.root.update_idletasks()
            
        except Exception as e:
            logging.error(f"❌ Buton durumu güncelleme hatası: {str(e)}")



def run_gui(async_loop):
    """GUI'yi başlatır"""
    try:
        app = ZilYonetimGUI(async_loop)  # school_type parametresini kaldırdık
        app.root.mainloop()
    except Exception as e:
        logging.critical(f"GUI çalıştırma hatası: {str(e)}", exc_info=True)
        raise