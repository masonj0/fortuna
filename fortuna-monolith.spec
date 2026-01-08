# -- mode: python ; coding: utf-8 --

"""
Fortuna Monolith - PyInstaller Spec
Single executable combining frontend + backend
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules
import os
import sys

block_cipher = None

print("[SPEC] Starting build configuration...")
print(f"[SPEC] Python: {sys.version}")
print(f"[SPEC] Working dir: {os.getcwd()}")

# Verify frontend exists
if not os.path.exists('frontend_dist'):
    print("[SPEC] ⚠️ WARNING: frontend_dist not found!")
    print("[SPEC] This is normal - it will be bundled at build time")

# ====================================================================
# COLLECT EVERYTHING FROM KEY PACKAGES
# ====================================================================
print("[SPEC] Collecting package data...")

uvicorn_data = collect_all('uvicorn')
fastapi_data = collect_all('fastapi')
starlette_data = collect_all('starlette')
pydantic_data = collect_all('pydantic')
webview_data = collect_all('webview')

print(f"[SPEC] Uvicorn: {len(uvicorn_data[0])} datas, {len(uvicorn_data[2])} imports")
print(f"[SPEC] FastAPI: {len(fastapi_data[0])} datas, {len(fastapi_data[2])} imports")
print(f"[SPEC] Starlette: {len(starlette_data[0])} datas, {len(starlette_data[2])} imports")

# ====================================================================
# DATA FILES - CRITICAL
# ====================================================================
datas = []

# Frontend (required)
if os.path.exists('frontend_dist'):
    datas.append(('frontend_dist', 'frontend_dist'))
    print("[SPEC] ✅ Added frontend_dist")

# Backend directories
backend_dirs = [
    'web_service/backend/data',
    'web_service/backend/json',
    'web_service/backend/config',
]

for directory in backend_dirs:
    if os.path.exists(directory):
        datas.append((directory, os.path.basename(directory)))
        print(f"[SPEC] Added {directory}")

# Package data files
datas += uvicorn_data[0]
datas += fastapi_data[0]
datas += starlette_data[0]
datas += pydantic_data[0]
datas += webview_data[0]

print(f"[SPEC] Total datas: {len(datas)}")

# ====================================================================
# BINARIES
# ====================================================================
binaries = []
binaries += uvicorn_data[1]
binaries += fastapi_data[1]
binaries += starlette_data[1]
binaries += webview_data[1]

print(f"[SPEC] Total binaries: {len(binaries)}")

# ====================================================================
# HIDDEN IMPORTS - MUST INCLUDE ALL ASYNC/HTTP SUPPORT
# ====================================================================
hiddenimports = [
    # Entry point
    'web_service.backend.monolith',

    # FastAPI/Starlette ecosystem
    'fastapi',
    'starlette',
    'starlette.middleware.cors',
    'starlette.staticfiles',
    'starlette.responses',

    # Async/HTTP core
    'h11',
    'httptools',
    'httpcore',
    'anyio',
    'anyio._backends._asyncio',
    'anyio.abc',

    # Web framework
    'uvicorn',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.loops.auto',

    # Data validation
    'pydantic',
    'pydantic.json',
    'pydantic_core',
    'pydantic_settings',

    # Async support
    'websockets',
    'websockets.frames',
    'wsproto',

    # GUI
    'webview',
    'webview.api',

    # Windows support
    'win32timezone',
    'pywin32',

    # Logging
    'logging.config',
    'structlog',
]

# Add collected imports
hiddenimports += uvicorn_data[2]
hiddenimports += fastapi_data[2]
hiddenimports += starlette_data[2]
hiddenimports += pydantic_data[2]
hiddenimports += webview_data[2]

# Try to collect backend submodules (won't error if empty)
try:
    backend_modules = collect_submodules('web_service.backend')
    hiddenimports += backend_modules
    print(f"[SPEC] Added {len(backend_modules)} backend submodules")
except:
    print("[SPEC] ⚠️ Could not collect backend submodules (may be OK)")

# Deduplicate
hiddenimports = list(dict.fromkeys(hiddenimports))
print(f"[SPEC] Total hidden imports: {len(hiddenimports)}")

# ====================================================================
# ANALYSIS
# ====================================================================
print("[SPEC] Running Analysis...")

# ====================================================================
# COLLECT EVERYTHING FROM KEY PACKAGES
# ====================================================================
print("[SPEC] Collecting package data...")

uvicorn_data = collect_all('uvicorn')
fastapi_data = collect_all('fastapi')
starlette_data = collect_all('starlette')
pydantic_data = collect_all('pydantic')
httpx_data = collect_all('httpx')
webview_data = collect_all('webview')

print(f"[SPEC] Uvicorn: {len(uvicorn_data[0])} datas, {len(uvicorn_data[2])} imports")
print(f"[SPEC] FastAPI: {len(fastapi_data[0])} datas, {len(fastapi_data[2])} imports")
print(f"[SPEC] Starlette: {len(starlette_data[0])} datas, {len(starlette_data[2])} imports")

# ====================================================================
# DATA FILES
# ====================================================================
datas = [
    ('frontend_dist', 'frontend_dist'),
]

# Add collected data files
datas += uvicorn_data[0]
datas += fastapi_data[0]
datas += starlette_data[0]
datas += pydantic_data[0]
datas += httpx_data[0]
datas += webview_data[0]

# Backend data directories (if they exist)
backend_data_dirs = [
    ('web_service/backend/data', 'data'),
    ('web_service/backend/json', 'json'),
    ('web_service/backend/adapters', 'adapters'),
    ('web_service/backend/config', 'config'),
    ('web_service/backend/prompts', 'prompts'),
    ('web_service/backend', 'backend'),  # Add root backend dir for full imports
]

for source, dest in backend_data_dirs:
    if os.path.exists(source):
        datas.append((source, dest))
        print(f"[SPEC] Including: {source} -> {dest}")

print(f"[SPEC] Total data files: {len(datas)}")

# ====================================================================
# BINARIES
# ====================================================================
binaries = []
binaries += uvicorn_data[1]
binaries += fastapi_data[1]
binaries += starlette_data[1]
binaries += webview_data[1]

# ====================================================================
# HIDDEN IMPORTS
# ====================================================================
hiddenimports = [
    # Core monolith
    'web_service.backend.monolith',

    # Try to include full API (but monolith works without it)
    'web_service.backend.api',
    'web_service.backend.engine',
    'web_service.backend.cache',
    'web_service.backend.config',

    # Essential HTTP/ASGI
    'h11',
    'httptools',
    'httpcore',
    'anyio._backends._asyncio',

    # Windows
    'win32timezone',
    'win32api',
    'win32con',

    # Logging
    'structlog',
    'logging.config',
    'websockets',
    'wsproto',
]

# Add collected hidden imports
hiddenimports += uvicorn_data[2]
hiddenimports += fastapi_data[2]
hiddenimports += starlette_data[2]
hiddenimports += pydantic_data[2]
hiddenimports += httpx_data[2]
hiddenimports += webview_data[2]

# Collect all submodules (nuclear option)
hiddenimports += collect_submodules('web_service.backend')

# Remove duplicates
hiddenimports = list(set(hiddenimports))
print(f"[SPEC] Total hidden imports: {len(hiddenimports)}")

# ====================================================================
# ANALYSIS
# ====================================================================
a = Analysis(
    ['web_service/backend/monolith.py'],
    pathex=[os.getcwd()],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ====================================================================
# EXECUTABLE - SINGLE FILE EXE
# ====================================================================
print("[SPEC] Building EXE...")

# ====================================================================
# EXECUTABLE
# ====================================================================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='FortunaMonolith',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Don't UPX - can cause issues
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # KEEP CONSOLE - needed to see startup messages
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

print("[SPEC] ✅ Spec configuration complete")
