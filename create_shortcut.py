import os
import sys
import win32com.client

def create_startup_shortcut():
    """Windows başlangıcına watchdog kısayolu ekler"""
    try:
        # Mevcut dizini bul
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        startup_path = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft\\Windows\\Start Menu\\Programs\\Startup'
        )
        
        # ⚠️ DÜZELTME: Doğru launcher yolunu belirle
        launcher_path = os.path.join(base_dir, "HayriBot_Launcher", "HayriBot_Launcher.exe")
        
        if not os.path.exists(launcher_path):
            # Alternatif yol dene
            launcher_path = os.path.join(base_dir, "HayriBot_Launcher.exe")
            if not os.path.exists(launcher_path):
                print("❌ Launcher hiçbir yerde bulunamadı!")
                return False
        
        # Kısayolu oluştur
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut_path = os.path.join(startup_path, "HayriBot_Watchdog.lnk")
        
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = launcher_path
        shortcut.WorkingDirectory = os.path.dirname(launcher_path)
        shortcut.Description = "HayriBot Watchdog - Uygulama izleyici"
        shortcut.IconLocation = launcher_path
        shortcut.save()
        
        print("✅ Watchdog başlangıç kısayolu oluşturuldu")
        print(f"   Hedef: {launcher_path}")
        return True
        
    except Exception as e:
        print(f"❌ Kısayol oluşturma hatası: {str(e)}")
        return False

if __name__ == "__main__":
    create_startup_shortcut()
    input("Devam etmek için Enter'a basın...")