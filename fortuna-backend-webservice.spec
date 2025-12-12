# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['web_service/backend/service_entry.py'],
    pathex=[],
    binaries=[],
    datas=[('web_service/backend', 'backend')],
    hiddenimports=['win32timezone', 'win32serviceutil', 'win32service', 'win32event'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fortuna-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fortuna-backend',
)
