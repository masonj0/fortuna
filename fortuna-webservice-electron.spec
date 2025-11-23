# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web_service/backend/adapters', 'adapters'),
    ],
    hiddenimports=[
        'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols',
        'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on',
        'fastapi.middleware', 'fastapi.middleware.cors',
        'starlette.middleware', 'starlette.middleware.cors',
        'pydantic_settings',
        'slowapi', 'slowapi.middleware', 'slowapi.util', 'slowapi.errors',
        'structlog', 'tenacity', 'httpx', 'aiosqlite',
        'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets.wsproto_impl', 'uvicorn.protocols.websockets.websockets_impl',
        'anyio._backends._asyncio', 'httpcore', 'python_multipart'
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
    name='fortuna-webservice-backend',
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
