# ============================================================================
# FILE: fortuna-backend-electron.spec
# FIXED: Includes ALL dependencies including structlog
# ============================================================================

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# CRITICAL FIX: Explicitly list ALL hidden imports
hidden_imports = [
    # FastAPI & ASGI server stack
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'fastapi',
    'fastapi.routing',
    'starlette',
    'starlette.applications',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.middleware.base',
    'starlette.staticfiles',
    'starlette.routing',

    # ⭐ STRUCTLOG - THE MISSING MODULE! ⭐
    'structlog',
    'structlog.processors',
    'structlog.dev',
    'structlog.stdlib',
    'structlog.contextvars',
    'structlog.testing',
    'structlog.threadlocal',

    # Async runtime
    'asyncio',
    'concurrent',
    'concurrent.futures',

    # HTTP & networking
    'httpx',
    'httpx._client',
    'httpx._config',
    'httpx._transports',
    'httptools',
    'websockets',
    'h11',
    'h2',
    'hpack',
    'hyperframe',
    'httpcore',

    # Data validation & settings
    'pydantic',
    'pydantic.fields',
    'pydantic.main',
    'pydantic.json',
    'pydantic_core',
    'pydantic_settings',
    'email_validator',

    # Database
    'sqlalchemy',
    'sqlalchemy.dialects',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.ext',
    'sqlalchemy.ext.asyncio',
    'sqlalchemy.pool',
    'aiosqlite',
    'greenlet',

    # Rate limiting & caching
    'slowapi',
    'limits',
    'redis',

    # Utilities
    'python_multipart',
    'python-dotenv',
    'click',
    'tenacity',
    'psutil',

    # Data processing (if used)
    'numpy',
    'pandas',
    'scipy',
    'beautifulsoup4',
    'selectolax',
    'soupsieve',

    # Image processing (if used)
    'PIL',
    'PIL.Image',
    'opencv-python',
    'cv2',
    'mss',

    # Crypto & security
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'keyring',
    'secretstorage',

    # Standard library (sometimes missed)
    'json',
    'logging',
    'logging.config',
    'logging.handlers',
    'pathlib',
    'os',
    'sys',
    're',
    'typing',
    'dataclasses',
    'datetime',
    'collections',
    'functools',
    'itertools',
]

# Collect all submodules from key packages
hidden_imports += collect_submodules('uvicorn')
hidden_imports += collect_submodules('fastapi')
hidden_imports += collect_submodules('starlette')
hidden_imports += collect_submodules('pydantic')
hidden_imports += collect_submodules('structlog')  # ← Add this!
hidden_imports += collect_submodules('sqlalchemy')

# Collect data files from packages that include static files
datas = []
datas += collect_data_files('starlette')
datas += collect_data_files('fastapi')
datas += collect_data_files('certifi')  # SSL certificates
datas += collect_data_files('tzdata')  # Timezone data

a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fortuna-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fortuna-backend',
)
