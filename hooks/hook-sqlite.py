
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
# SQLite3 için DLL'leri ve veri dosyalarını topla
binaries = collect_dynamic_libs('sqlite3')
datas = collect_data_files('sqlite3')


