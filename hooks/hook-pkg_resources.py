
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

# pkg_resources için veri dosyalarını ve alt modülleri topla
datas = collect_data_files('pkg_resources')
hiddenimports = collect_submodules('pkg_resources')

# Manuel olarak jaraco.text bağımlılığını ekle (gerekirse)
datas.append((os.path.join('data', 'Lorem ipsum.txt'), 'jaraco/text'))
