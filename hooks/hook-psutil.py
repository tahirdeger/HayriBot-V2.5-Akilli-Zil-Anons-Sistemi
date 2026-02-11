
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('psutil')

#BİTTİ ***hooks/hook-psutil.py***