# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from pathlib import Path
import sys
import os

block_cipher = None

# Absolute paths avoid CI confusion
project_root = Path(os.getcwd()).absolute()
backend_root = project_root / 'web_service' / 'backend'
frontend_out = project_root / 'web_service' / 'frontend' / 'public'

print(f"[SPEC] Project Root: {project_root}")
print(f"[SPEC] Frontend: {frontend_out}")

if not frontend_out.exists():
    print("[SPEC] WARNING: Frontend public dir not found. Build might fail at runtime.")

datas = [
    (str(frontend_out), 'public'),
    (str(backend_root / 'data'), 'web_service/backend/data'),
    (str(backend_root / 'json'), 'web_service/backend/json')
]

# Collect Uvicorn & FastAPI internals
datas += collect_data_files('uvicorn')
datas += collect_data_files('fastapi')

hiddenimports = [
    'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.lifespan.on',
    'fastapi', 'starlette', 'pydantic', 'structlog', 'tenacity',
    'webview', 'webview.platforms.winforms', 'clr',
    'win32timezone', 'win32service', 'win32event', 'servicemanager'
]
hiddenimports += collect_submodules('web_service.backend')

a = Analysis(
    ['run_desktop_app.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Fortuna-Desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # GUI Mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)