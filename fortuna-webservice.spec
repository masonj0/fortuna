# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(SPECPATH).resolve()

def include_tree(rel_path, target, store):
    absolute = project_root / rel_path
    if absolute.exists():
        store.append((str(absolute), target))
        print(f"[spec] Including {absolute} -> {target}")
    else:
        # This spec is used by the legacy build-msi.yml, which checks for these dirs.
        # If they are missing here, it's a critical error.
        raise FileNotFoundError(f"[spec] Required directory not found: {absolute}")

datas = []
# Paths must match the legacy structure used by build-msi.yml
include_tree('python_service/adapters', 'adapters', datas)
include_tree('python_service/data', 'data', datas)
include_tree('python_service/json', 'json', datas)

# Collect library assets
try:
    datas += collect_data_files('uvicorn', includes=['*.html', '*.json'])
    datas += collect_data_files('structlog', includes=['*.json'])
except Exception as e:
    print(f"[spec] Warning: Could not collect library data files: {e}")

# Collect Hidden Imports for python_service
hidden_imports = set()
hidden_imports.update(collect_submodules('python_service'))
hidden_imports.update([
    'fastapi', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.lifespan.on',
    'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets.wsproto_impl', 'uvicorn.protocols.websockets.websockets_impl',
    'anyio', 'httpcore', 'httpx', 'python_multipart', 'pydantic', 'pydantic_core',
    'aiosqlite', 'structlog', 'tenacity', 'slowapi'
])

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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='fortuna-webservice', # Name matches the workflow expectation
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
