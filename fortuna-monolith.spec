# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [('frontend_dist', 'frontend_dist')]
datas += collect_data_files('uvicorn')
datas += collect_data_files('fastapi')
datas += collect_data_files('starlette')

hiddenimports = [
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
]
hiddenimports.extend(collect_submodules('uvicorn'))
hiddenimports.extend(collect_submodules('fastapi'))
hiddenimports.extend(collect_submodules('starlette'))
hiddenimports.extend(collect_submodules('anyio'))
hiddenimports.append('win32timezone')
hiddenimports.extend(['pydantic_settings.sources'])

a = Analysis(
    ['web_service/backend/monolith.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fortuna-monolith',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to True for debugging stdout
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fortuna-monolith'
)
