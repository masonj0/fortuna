# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(__file__).resolve().parent

def include(rel_path: str, target: str, container: list):
    source = project_root / rel_path
    if source.exists():
        container.append((str(source), target))
        print(f"[spec] Including {source} -> {target}")
    else:
        print(f"[spec] Missing optional path: {source}")

datas = []
hiddenimports = set()

include('python_service/data', 'data', datas)
include('python_service/json', 'json', datas)
include('python_service/adapters', 'adapters', datas)
include('python_service/config', 'config', datas)

datas += collect_data_files('python_service', includes=['*.json', '*.yml', '*.yaml'])
hiddenimports.update(collect_submodules('python_service'))
hiddenimports.update([
    'asyncio',
    'asyncio.windows_events',
    'asyncio.selector_events',
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
    'pydantic_core',
    'pydantic_settings.sources',
    'anyio._backends._asyncio',
    'httpcore',
    'python_multipart',
    'numpy',
    'pandas',
])

a = Analysis(
    ['python_service/main.py'],
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
    name='fortuna-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
