
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Tüm apscheduler modüllerini topla
hiddenimports = collect_submodules('apscheduler')

# Apscheduler için gerekli veri dosyalarını topla
datas = collect_data_files('apscheduler', includes=['**/*.py'])

# Özellikle trigger'lar için manuel importlar
hiddenimports.extend([
    'apscheduler.triggers.cron',
    'apscheduler.triggers.interval', 
    'apscheduler.triggers.date',
    'apscheduler.triggers.combining',
    'apscheduler.triggers.base'
])