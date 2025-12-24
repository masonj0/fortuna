# ============================================================================
# FILE: fortuna-backend-electron.spec
# FIXED: Includes all dependencies needed for PyInstaller bundle
# ============================================================================

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# CRITICAL FIX: Explicitly list ALL hidden imports
# These won't be found by PyInstaller's import scanning
hidden_imports = [
    # FastAPI & ASGI server stack
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websocket',
    'fastapi',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.staticfiles',

    # Async runtime
    'asyncio',
    'concurrent',
    'concurrent.futures',

    # HTTP & networking
    'httpx',
    'httptools',
    'websockets',

    # Data validation
    'pydantic',
    'pydantic.json',
    'email_validator',

    # Standard library (sometimes missed)
    'json',
    'logging',
    'pathlib',
    'os',
    'sys',
    're',
    'typing',
    'dataclasses',

    # Common utilities
    'python-dotenv',
    'click',
]

# Collect all submodules from key packages
hidden_imports += collect_submodules('uvicorn')
hidden_imports += collect_submodules('fastapi')
hidden_imports += collect_submodules('starlette')
hidden_imports += collect_submodules('pydantic')

# Collect data files from packages that include static files
datas = []
datas += collect_data_files('starlette')
datas += collect_data_files('fastapi')

a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,  # ← NOW POPULATED!
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
