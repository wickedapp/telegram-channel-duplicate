# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Volumes/DATA/Development/telegram-channel-duplicate/dist_obfuscated/installer/tray_app.py'],
    pathex=[],
    binaries=[],
    datas=[('/Volumes/DATA/Development/telegram-channel-duplicate/dist_obfuscated/src', 'src'), ('/Volumes/DATA/Development/telegram-channel-duplicate/config.yaml.template', '.'), ('/Volumes/DATA/Development/telegram-channel-duplicate/.env.template', '.'), ('/Volumes/DATA/Development/telegram-channel-duplicate/installer/assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Telegram转发助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['/Volumes/DATA/Development/telegram-channel-duplicate/installer/assets/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Telegram转发助手',
)
app = BUNDLE(
    coll,
    name='Telegram转发助手.app',
    icon='/Volumes/DATA/Development/telegram-channel-duplicate/installer/assets/icon.ico',
    bundle_identifier=None,
)
