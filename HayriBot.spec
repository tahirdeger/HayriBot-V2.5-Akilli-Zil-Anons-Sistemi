# HayriBot.spec
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

added_files = [
    ('models',          'models'),
    ('media',           'media'),
    ('data',            'data'),
    ('config',          'config'),
    ('dlls\\plugins',   'plugins'),
    ('dlls\\zoneinfo',  'zoneinfo'),
    ('dlls\\cacert.pem', '.'),
]

added_files += collect_data_files('piper')
added_files += collect_data_files('onnxruntime')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        # VLC çekirdek — PyInstaller bunları bilmez
        ('dlls\\libvlc.dll',         '.'),
        ('dlls\\libvlccore.dll',     '.'),
        ('dlls\\npvlc.dll',          '.'),
        ('dlls\\zlib1.dll',          '.'),
        # sqlite3.dll — _sqlite3.pyd'nin bağımlılığı
        ('dlls\\sqlite3.dll',        '.'),
    ],
    datas=added_files,
    hiddenimports=[
        'piper',
        'onnxruntime',
        'onnxruntime.capi._pybind_state',
        'edge_tts',
        'vlc',
        'apscheduler.schedulers.background',
        'apscheduler.executors.pool',
        'apscheduler.jobstores.sqlalchemy',
        'telegram',
        'telegram.ext',
        'pymitter',
        'customtkinter',
        'pystray',
        'PIL',
        'PIL._tkinter_finder',
        'win32api', 'win32con', 'win32gui',
        'pytz', 'tzdata',
        'filelock',
        'aiohttp',
        'sqlite3',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy.testing', 'pytest', 'IPython'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HayriBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='media\\app_icon.ico',
    contents_directory='.',   # PyInstaller 6.x: _internal yok, her şey EXE yanına
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['libvlc.dll', 'libvlccore.dll'],
    name='HayriBot',
)
