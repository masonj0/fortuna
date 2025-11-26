# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(SPECPATH)

def include_tree(rel_path: str, target: str, store: list):
    absolute = project_root / rel_path
    if absolute.exists():
        store.append((str(absolute), target))
        print(f"[spec] Including {absolute} -> {target}")
    else:
        print(f"[spec] Skipping missing include: {absolute}")

datas = []
hiddenimports = set()

include_tree('web_service/frontend/out', 'ui', datas)
include_tree('web_service/backend/adapters', 'adapters', datas)
include_tree('web_service/backend/data', 'data', datas)
include_tree('web_service/backend/json', 'json', datas)
include_tree('web_service/backend/templates', 'templates', datas)

datas += collect_data_files('uvicorn', includes=['*.html', '*.json'])
datas += collect_data_files('slowapi', includes=['*.json', '*.yaml'])
datas += collect_data_files('structlog', includes=['*.json'])
hiddenimports.update(collect_submodules('web_service'))
hiddenimports.update(collect_submodules('web_service.backend'))
hiddenimports.update([
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan.on',
    'fastapi.routing',
    'fastapi.middleware.cors',
    'starlette.staticfiles',
    'starlette.middleware.cors',
    'anyio._backends._asyncio',
    'httpcore',
    'httpx',
    'python_multipart',
    'slowapi',
    'structlog',
    'tenacity',
    'aiosqlite',
    'selectolax',
    'pydantic_core',
    'pydantic_settings.sources',
])

a = Analysis(
    ['run_web_service.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=sorted(hiddenimports),
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
    [],
    name='fortuna-webservice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
