
import os
import sys
from pathlib import Path  # ← EKLE: Path desteği için
import logging

def get_base_directory():
    """Temel dizin yolunu döndürür"""
    if getattr(sys, 'frozen', False):
        # EXE modunda: executable'ın olduğu dizin
        return Path(os.path.dirname(sys.executable))  # ← DEĞİŞTİR: Path objesi
    else:
        # Geliştirme modunda: script'in olduğu dizin
        return Path(os.path.dirname(os.path.abspath(__file__)))  # ← DEĞİŞTİR: Path objesi

def get_media_path(filename=None):
    """Media dosya yolunu döndürür"""
    base_dir = get_base_directory()
    
    # Olası media yolları
    possible_paths = [
        base_dir / 'media',  # ← DEĞİŞTİR: Path join
        base_dir.parent / 'media',  # ← DEĞİŞTİR: Üst dizin (HayriBot_Final/media)
        base_dir / 'HayriBot' / 'media',
        base_dir.parent / 'HayriBot_Final' / 'media',
    ]
    
    for media_path in possible_paths:
        if media_path.is_dir():  # ← DEĞİŞTİR: Path.is_dir()
            if filename:
                file_path = media_path / filename  # ← DEĞİŞTİR: Path join
                if file_path.exists():  # ← DEĞİŞTİR: Path.exists()
                    return file_path
            else:
                return media_path
    
    # Media klasörü bulunamazsa
    logging.warning(f"Media klasörü bulunamadı. Aranan yerler: {possible_paths}")
    if filename:
        return base_dir / filename  # ← DEĞİŞTİR: Fallback Path
    return base_dir

def get_data_path(filename=None):
    """Data dosya yolunu döndürür"""
    base_dir = get_base_directory()
    
    # Olası data yolları
    possible_paths = [
        base_dir / 'data',  # ← DEĞİŞTİR: Path join
        base_dir.parent / 'data',  # ← DEĞİŞTİR: Üst dizin
        base_dir / 'HayriBot' / 'data',
        base_dir.parent / 'HayriBot_Final' / 'data',
    ]
    
    for data_path in possible_paths:
        if data_path.is_dir():  # ← DEĞİŞTİR: Path.is_dir()
            if filename:
                file_path = data_path / filename  # ← DEĞİŞTİR: Path join
                if file_path.exists():  # ← DEĞİŞTİR: Path.exists()
                    return file_path
            else:
                return data_path
    
    # Data klasörü bulunamazsa
    logging.warning(f"Data klasörü bulunamadı. Aranan yerler: {possible_paths}")
    if filename:
        return base_dir / filename  # ← DEĞİŞTİR: Fallback Path
    return base_dir

def find_file(filename, search_dirs=None):
    """Dosyayı farklı dizinlerde ara"""
    if search_dirs is None:
        search_dirs = [
            get_base_directory(),
            get_media_path(),
            get_data_path(),
            get_base_directory().parent,  # ← DEĞİŞTİR: Path.parent
        ]
    
    for search_dir in search_dirs:
        if search_dir and search_dir.is_dir():  # ← DEĞİŞTİR: Path.is_dir()
            file_path = search_dir / filename  # ← DEĞİŞTİR: Path join
            if file_path.exists():  # ← DEĞİŞTİR: Path.exists()
                return file_path
    
    return None

# Test fonksiyonu
def test_paths():
    """Yolları test et"""
    print("🔍 Dosya Yolu Testi")
    print("=" * 50)
    print(f"Temel Dizin: {get_base_directory()}")
    print(f"Media Dizin: {get_media_path()}")
    print(f"Data Dizin: {get_data_path()}")
    
    # Test dosyaları
    test_files = ['anons.mp3', 'tgmesaj.mp3', 'zil_db.sqlite']
    for file in test_files:
        path = find_file(file)
        if path:
            print(f"✅ {file}: {path}")
        else:
            print(f"❌ {file}: BULUNAMADI")


def get_model_path(model_name="tts_models--multilingual--multi-dataset--xtts_v2"):
    """TTS model yolunu döndürür"""
    base_dir = get_base_directory()
    
    possible_paths = [
        base_dir / 'models' / model_name,
        base_dir.parent / 'models' / model_name,
        base_dir / 'HayriBot' / 'models' / model_name,
    ]
    
    for model_path in possible_paths:
        if model_path.is_dir():
            config_file = model_path / 'config.json'
            if config_file.exists():
                return model_path
    
    logging.warning(f"Model klasörü bulunamadı: {model_name}")
    return base_dir / 'models' / model_name

if __name__ == "__main__":
    test_paths()