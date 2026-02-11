
from PyInstaller.utils.hooks import collect_data_files

# jaraco.text modülünün tüm veri dosyalarını topla
datas = collect_data_files('jaraco.text', include_py_files=True)


