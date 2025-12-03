# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(SPECPATH).parent

# Helper function to include data files
def include(rel_path: str, target: str, store: list):
    absolute = project_root / rel_path
    if absolute.exists():
        store.append((str(absolute), target))
    else:
        print(f"[spec] WARNING: Skipping missing include: {absolute}")

datas = []
hiddenimports = set()

# Include necessary data directories
include('python_service/data', 'data', datas)
include('python_service/json', 'json', datas)
include('python_service/adapters', 'adapters', datas)

# Automatically collect submodules and data files for key libraries
datas += collect_data_files('uvicorn')
datas += collect_data_files('fastapi')
datas += collect_data_files('starlette')
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
    'httpx',
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

# ☢️ PYZ INJECTION: Force __init__ files into the PYZ archive as modules
# This is the definitive fix for ModuleNotFoundError at runtime.
a.pure += [
    ('python_service', str(project_root / 'python_service/__init__.py'), 'PYMODULE'),
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
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
