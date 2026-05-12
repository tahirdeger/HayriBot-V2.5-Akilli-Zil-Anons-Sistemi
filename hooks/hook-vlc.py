
from PyInstaller.utils.hooks import collect_dynamic_libs

# VLC DLL'lerini topla
binaries = collect_dynamic_libs('vlc')

# VLC eklentilerini de ekle
import os
import vlc
if hasattr(vlc, '__path__'):
    vlc_path = vlc.__path__[0]
    for root, dirs, files in os.walk(vlc_path):
        for file in files:
            if file.endswith(('.dll', '.so', '.dylib')):
                full_path = os.path.join(root, file)
                binaries.append((full_path, 'vlc'))