# fortuna-webservice.spec
# This is the single, authoritative PyInstaller spec file for building the web service.
import os

block_cipher = None

# Consolidate all data assets required by any of the build targets.
# The path is relative to the root, where this spec file lives.
datas = []

# 1. Add frontend assets
frontend_path = 'web_service/frontend/out'
if os.path.exists(frontend_path):
    datas.append((frontend_path, 'ui'))

# 2. Add backend adapters
adapters_path = 'web_service/backend/adapters'
if os.path.exists(adapters_path):
    datas.append((adapters_path, 'adapters'))

# Consolidate all hidden imports from all previous spec files into a single superset.
hiddenimports = [
    # Core Uvicorn/FastAPI
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan.on',
    'fastapi.routing',
    'fastapi.middleware.cors',

    # Explicit package imports to resolve ModuleNotFoundError
    'web_service',
    'web_service.backend',
    'web_service.backend.api',
    'starlette.staticfiles',
    'starlette.middleware.cors',

    # Core Pydantic
    'pydantic_core',
    'pydantic_settings.sources',

    # Core Async/HTTP
    'anyio._backends._asyncio',
    'httpcore',
    'httpx',

    # Utility Libraries
    'python_multipart',
    'slowapi',
    'slowapi.middleware',
    'slowapi.util',
    'slowapi.errors',
    'structlog',
    'tenacity',
    'aiosqlite',
    'selectolax',

    # Data Science Libraries (from older spec files, included for safety)
    'numpy',
    'pandas',
]

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
