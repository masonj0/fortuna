# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).parent

a = Analysis(
    ['python_service/main.py'],  # ✅ CHANGED from run_electron_service.py
    pathex=['.'],
    binaries=[],
    datas=[
        (str(project_root / 'python_service/data'), 'data'),
        (str(project_root / 'python_service/json'), 'json'),
        (str(project_root / 'python_service/adapters'), 'adapters'),
    ],
    hiddenimports=[
        # Event loop support
        'asyncio',
        'asyncio.windows_events',
        'asyncio.selector_events',

        # Uvicorn/FastAPI
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

        # Package structure
        'python_service',
        'python_service.backend',
        'python_service.backend.api',

        'numpy',
        'pandas'
    ],
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
