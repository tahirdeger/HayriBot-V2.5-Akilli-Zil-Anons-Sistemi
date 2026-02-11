
import os
import sys
import logging
import tkinter as tk
from tkinter import messagebox
import win32com.client
from win32com.client import Dispatch
from utils.database import ayar_getir, ayar_kaydet

def check_and_ask_startup():
    """İlk çalıştırmada başlangıç sorusunu sor"""
    try:
        from utils.database import is_first_run
        
        # Sadece ilk çalıştırmada veya daha önce sorulmadıysa sor
        if is_first_run() or ayar_getir("startup_asked") != "1":
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            
            response = messagebox.askyesno(
                "Başlangıç Ayarı",
                "Windows açılışında uygulama otomatik başlatılsın mı?\n\n"
                "(Bu ayarı sonradan uygulama ayarlarından değiştirebilirsiniz)"
            )
            
            if response:
                if add_to_startup():
                    ayar_kaydet("startup_enabled", "1")
                else:
                    messagebox.showerror("Hata", "Başlangıca ekleme başarısız!")
            else:
                remove_from_startup()
                ayar_kaydet("startup_enabled", "0")
                
            ayar_kaydet("startup_asked", "1")
            root.destroy()
    except Exception as e:
        logging.error(f"Başlangıç sorusu hatası: {str(e)}")

def add_to_startup():
    """Başlangıca ekleme işlemini yapar. Başarı durumunu döndürür."""
    try:
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
            working_dir = os.path.dirname(exe_path)
        else:
            exe_path = os.path.abspath(sys.argv[0])
            working_dir = os.path.dirname(exe_path)

        startup_path = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft\\Windows\\Start Menu\\Programs\\Startup'
        )
        shortcut_path = os.path.join(startup_path, 'HayriAsistan.lnk')

        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = exe_path
        shortcut.WorkingDirectory = working_dir
        shortcut.IconLocation = os.path.join(working_dir, 'media', 'app_icon.ico')
        shortcut.save()
        logging.info("✅ Başlangıç kısayolu eklendi")
        return True
    except Exception as e:
        logging.error(f"❌ Kısayol oluşturma hatası: {str(e)}")
        return False

def remove_from_startup():
    """Başlangıçtan kaldırma işlemini yapar. Başarı durumunu döndürür."""
    try:
        startup_path = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft\\Windows\\Start Menu\\Programs\\Startup',
            'HayriAsistan.lnk'
        )
        if os.path.exists(startup_path):
            os.remove(startup_path)
            logging.info("✅ Başlangıç kısayolu kaldırıldı")
            return True
        else:
            logging.info("Başlangıç kısayolu zaten mevcut değil")
            return True  # Dosya yoksa işlem başarılı sayılır
    except PermissionError as e:
        logging.warning(f"⚠️ Başlangıç kısayolu silinemedi, yönetici izni gerekebilir: {str(e)}")
        messagebox.showerror(
            "Hata",
            "Başlangıç ayarı değiştirilemedi.\n"
            "Lütfen uygulamayı yönetici olarak çalıştırıp tekrar deneyin."
        )
        return False
    except Exception as e:
        logging.error(f"❌ Başlangıç kısayolu silme hatası: {str(e)}", exc_info=True)
        messagebox.showerror(
            "Hata",
            f"Başlangıç ayarı değiştirilemedi: {str(e)}\n"
            "Lütfen destek ekibiyle iletişime geçin."
        )
        return False
