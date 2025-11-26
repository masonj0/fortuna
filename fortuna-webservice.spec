# fortuna-webservice.spec
import os
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).parent

datas = []

# 1. Add frontend assets
frontend_path = project_root / 'web_service/frontend/out'
if frontend_path.exists():
    datas.append((str(frontend_path), 'ui'))

# 2. Add backend adapters
adapters_path = project_root / 'web_service/backend/adapters'
if adapters_path.exists():
    datas.append((str(adapters_path), 'adapters'))

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl', 'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.protocols.websockets.websockets_impl', 'uvicorn.lifespan.on',
    'fastapi.routing', 'fastapi.middleware.cors',
    'anyio._backends._asyncio', 'httpcore', 'httpx',
    'python_multipart', 'slowapi', 'structlog', 'tenacity', 'aiosqlite', 'selectolax',
    'pydantic_core', 'pydantic_settings.sources',
    'python_service.port_check'  # Added from run_web_service.py
]
hiddenimports += collect_submodules('web_service')

a = Analysis(
    ['run_web_service.py'],
    pathex=['.'],
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
    [],
    name='fortuna-webservice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # CRITICAL for Service stability
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # CRITICAL: No window for Services
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
