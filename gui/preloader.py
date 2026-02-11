#*gui/preloader.py*
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys
from utils.database import ayar_kaydet, init_db
import logging

class PreloaderWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("HayriBotV1.4 - Yükleniyor")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        self.root.configure(bg='white')
        
        # Pencereyi ortala
        self.center_window()
        
        self.setup_ui()

    def center_window(self):
        """Pencereyi ekranın ortasına yerleştir"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")

    def setup_ui(self):
        # Başlık
        title_label = tk.Label(
            self.root, 
            text="HayriBotV2 | 2025 | islematolyesi.odoo.com",
            font=("Arial", 12, "bold"),
            fg="black",
            bg='white'
        )
        title_label.pack(pady=20)
        
        # İlerleme çubuğu
        self.progress = ttk.Progressbar(
            self.root, 
            orient="horizontal", 
            length=400, 
            mode="determinate"
        )
        self.progress.pack(pady=20)
        
        # Durum metni
        self.status_label = tk.Label(
            self.root,
            text="Sistem hazırlanıyor...",
            font=("Arial", 10),
            fg="black",
            bg='white'
        )
        self.status_label.pack(pady=10)
        
        # Okul türü seçim frame
        school_frame = tk.LabelFrame(
            self.root, 
            text="Okul Türünü Seçin",
            font=("Arial", 10, "bold"),
            bg='white'
        )
        school_frame.pack(pady=20, padx=40, fill="x")
        
        # Okul türü seçenekleri
        self.school_type = tk.StringVar(value="normal")
        
        tk.Radiobutton(
            school_frame, 
            text="Normal Okul", 
            variable=self.school_type, 
            value="normal",
            font=("Arial", 10),
            bg='white'
        ).pack(anchor="w", pady=5)
        
        tk.Radiobutton(
            school_frame, 
            text="İmam Hatip Okulu", 
            variable=self.school_type, 
            value="imam_hatip",
            font=("Arial", 10),
            bg='white'
        ).pack(anchor="w", pady=5)
        
        # Devam butonu
        self.continue_btn = tk.Button(
            school_frame,
            text="Devam Et",
            command=self.on_continue,
            state="disabled",
            font=("Arial", 10)
        )
        self.continue_btn.pack(pady=10)
        
    def update_progress(self, value, text):
        self.progress['value'] = value
        self.status_label.config(text=text)
        self.root.update_idletasks()
        
    def start_loading(self):
        def loading_process():
            # Veritabanı yükleniyor
            self.update_progress(20, "Veritabanı yükleniyor...")
            try:
                init_db()
                time.sleep(0.5)
            except Exception as e:
                messagebox.showerror("Hata", f"Veritabanı yüklenemedi: {str(e)}")
                self.root.quit()
                return
            
            # Sistem ayarları kontrol ediliyor
            self.update_progress(40, "Sistem ayarları kontrol ediliyor...")
            time.sleep(0.5)
            
            # Medya dosyaları kontrol ediliyor
            self.update_progress(60, "Medya dosyaları kontrol ediliyor...")
            time.sleep(0.5)
            
            # Telegram ayarları kontrol ediliyor
            self.update_progress(80, "Telegram ayarları kontrol ediliyor...")
            time.sleep(0.5)
            
            # Yükleme tamamlandı, devam butonunu aktif et
            self.update_progress(100, "Hazır! Okul türünü seçin ve Devam Et'e tıklayın")
            
            # Devam butonunu aktif et
            self.root.after(0, lambda: self.continue_btn.config(state="normal"))
            
        threading.Thread(target=loading_process, daemon=True).start()
        
    def on_continue(self):
        # Seçilen okul türünü kaydet
        school_type = self.school_type.get()
        ayar_kaydet("school_type", school_type)
        
        # Pencereyi kapat ve ana uygulamayı başlat
        self.root.quit()
        self.root.destroy()
        
    def run(self):
        # İlk çalıştırma kontrolü
        from utils.database import is_first_run
        
        if is_first_run():
            # İlk çalıştırma - preloader göster
            self.root.after(100, self.start_loading)
            self.root.mainloop()
            return self.school_type.get()
        else:
            # Sonraki çalıştırmalar - doğrudan kayıtlı okul türünü döndür
            from utils.database import ayar_getir
            return ayar_getir("school_type", "normal")