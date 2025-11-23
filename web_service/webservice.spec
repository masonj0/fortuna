# webservice.spec
from PyInstaller.utils.hooks import collect_data_files
import os

block_cipher = None

# Collect frontend build output
frontend_datas = []
frontend_out = 'frontend/out'
if os.path.exists(frontend_out):
    frontend_datas = [(frontend_out, 'ui')]

a = Analysis(
    ['web_service/backend/run_web_service_backend.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../python_service', 'python_service'),
        *frontend_datas,
    ],
    hiddenimports=[
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
        'aiosqlite',
        'structlog',
        'slowapi',
        'slowapi.middleware',
        'slowapi.util',
        'httpx',
        'tenacity',
        'selectolax'
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
    name='fortuna-webservice',
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
