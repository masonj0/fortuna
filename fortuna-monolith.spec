# -*- mode: python ; coding: utf-8 -*-
"""
Fortuna Monolith - PyInstaller Spec
Single executable combining Next.js frontend + FastAPI backend
Production-grade configuration with security, performance, and maintainability
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules
import os
import sys

# ====================================================================
# CONFIGURATION
# ====================================================================
APP_NAME = "fortuna-monolith"
CONSOLE_MODE = True  # Set to False for windowed-only app
OPTIMIZE_LEVEL = 2  # 0=none, 1=basic, 2=full (slower build, faster runtime)

# ====================================================================
# BUILD OUTPUT
# ====================================================================
print("[SPEC] " + "=" * 66)
print(f"[SPEC] Fortuna Monolith PyInstaller Configuration")
print(f"[SPEC] Python: {sys.version.split()[0]}")
print(f"[SPEC] Platform: {sys.platform}")
print(f"[SPEC] Working dir: {os.getcwd()}")
print("[SPEC] " + "=" * 66)

# ====================================================================
# VERIFY PREREQUISITES
# ====================================================================
prerequisites = {
    'frontend_dist': 'Frontend static files',
    'web_service/backend/monolith.py': 'Monolith entry point',
    'web_service/backend/requirements.txt': 'Python dependencies list',
}

print("[SPEC] Checking prerequisites...")
missing = []
for path, description in prerequisites.items():
    exists = os.path.exists(path)
    status = "FOUND" if exists else "MISSING"
    print(f"[SPEC]   {description}: {status}")
    if not exists:
        missing.append(path)

if missing:
    print(f"[SPEC] WARNING: Missing files - build may fail:")
    for path in missing:
        print(f"[SPEC]   - {path}")

# ====================================================================
# COLLECT PACKAGE DATA & HOOKS
# ====================================================================
print("[SPEC] Collecting package metadata...")

# Collect data from all FastAPI/web dependencies
packages_to_collect = {
    'uvicorn': 'ASGI server',
    'fastapi': 'Web framework',
    'starlette': 'ASGI toolkit',
    'pydantic': 'Data validation',
    'webview': 'GUI framework',
}

collected_data = {}
for package, description in packages_to_collect.items():
    try:
        data = collect_all(package)
        collected_data[package] = data
        datas_count = len(data[0])
        imports_count = len(data[2])
        print(f"[SPEC]   {package}: {datas_count} data files, {imports_count} imports")
    except Exception as e:
        print(f"[SPEC]   WARNING: Failed to collect {package}: {e}")
        collected_data[package] = ([], [], [])

# ====================================================================
# DATA FILES (CRITICAL FOR RUNTIME)
# ====================================================================
print("[SPEC] Configuring data files...")
datas = []

# Frontend static files (required)
if os.path.exists('frontend_dist'):
    datas.append(('frontend_dist', 'frontend_dist'))
    print("[SPEC]   Added: frontend_dist -> frontend_dist")
else:
    print("[SPEC]   WARNING: frontend_dist not found (will be created at build time)")

# Backend runtime directories
backend_dirs = [
    ('web_service/backend/data', 'data'),
    ('web_service/backend/json', 'json'),
    ('web_service/backend/logs', 'logs'),
    ('web_service/backend/config', 'config'),
]

for source_dir, dest_dir in backend_dirs:
    if os.path.exists(source_dir):
        datas.append((source_dir, dest_dir))
        print(f"[SPEC]   Added: {source_dir} -> {dest_dir}")

# Collect package data files from dependencies
for package, data in collected_data.items():
    datas.extend(data[0])

print(f"[SPEC] Total data files: {len(datas)}")

# ====================================================================
# BINARIES (DYNAMIC LIBRARIES)
# ====================================================================
print("[SPEC] Configuring binaries...")
binaries = []

for package, data in collected_data.items():
    binaries.extend(data[1])

print(f"[SPEC] Total binaries: {len(binaries)}")

# ====================================================================
# HIDDEN IMPORTS (MODULES NOT DETECTED BY STATIC ANALYSIS)
# ====================================================================
print("[SPEC] Configuring hidden imports...")

hiddenimports = [
    # Application entry points
    'web_service.backend.monolith',

    # FastAPI ecosystem
    'fastapi',
    'fastapi.openapi',
    'starlette.middleware.cors',
    'starlette.middleware.base',
    'starlette.staticfiles',
    'starlette.responses',
    'starlette.routing',

    # Async/HTTP infrastructure
    'h11',
    'httptools',
    'httpcore',
    'anyio',
    'anyio._backends._asyncio',
    'anyio._backends._trio',
    'anyio.abc',

    # ASGI server
    'uvicorn',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.loops',
    'uvicorn.loops.auto',

    # Data validation
    'pydantic',
    'pydantic.json',
    'pydantic_core',
    'pydantic_settings',
    'pydantic.validators',

    # WebSocket support
    'websockets',
    'websockets.frames',
    'websockets.protocol',
    'wsproto',
    'wsproto.frame_builder',

    # GUI rendering
    'webview',
    'webview.api',
    'webview.dom',

    # Windows-specific
    'win32timezone',
    'pywin32',
    'win32api',
    'win32con',

    # Logging and monitoring
    'logging.config',
    'structlog',
    'structlog.stdlib',

    # JSON encoding/decoding
    'json',
    'json.decoder',
    'json.encoder',

    # Standard library items that might be missed
    'pathlib',
    'contextlib',
    'io',
    'threading',
    'collections.abc',
]

# Add collected hidden imports from packages
for package, data in collected_data.items():
    hiddenimports.extend(data[2])

# Try to collect backend submodules
print("[SPEC] Scanning for additional backend modules...")
try:
    backend_submodules = collect_submodules('web_service.backend')
    hiddenimports.extend(backend_submodules)
    print(f"[SPEC]   Found {len(backend_submodules)} backend submodules")
except Exception as e:
    print(f"[SPEC]   WARNING: Could not scan backend submodules: {e}")

# Remove duplicates while preserving order
hiddenimports = list(dict.fromkeys(hiddenimports))
print(f"[SPEC] Total hidden imports: {len(hiddenimports)}")

# ====================================================================
# ANALYSIS PHASE
# ====================================================================
print("[SPEC] " + "=" * 66)
print("[SPEC] Starting PyInstaller analysis...")
print("[SPEC] " + "=" * 66)

a = Analysis(
    ['web_service/backend/monolith.py'],
    pathex=[os.getcwd()],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'sklearn',
        'torch',
        'tensorflow',
        'pytest',
        'unittest',
        'bdb',
        'pdb',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ====================================================================
# BUILD EXECUTABLE
# ====================================================================
print("[SPEC] " + "=" * 66)
print("[SPEC] Building executable...")
print("[SPEC] " + "=" * 66)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can cause runtime issues, disabled for stability
    upx_exclude=[],
    runtime_tmpdir=None,
    console=CONSOLE_MODE,  # Keep console for debugging output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Set to 'path/to/icon.ico' for custom icon
)

# ====================================================================
# BUILD COMPLETE
# ====================================================================
print("[SPEC] " + "=" * 66)
print("[SPEC] Build configuration complete!")
print("[SPEC] " + "=" * 66)
print("[SPEC]")
print("[SPEC] Summary:")
print(f"[SPEC]   Output: dist/{APP_NAME}.exe")
print(f"[SPEC]   Data files: {len(datas)}")
print(f"[SPEC]   Binaries: {len(binaries)}")
print(f"[SPEC]   Hidden imports: {len(hiddenimports)}")
print("[SPEC]")
print("[SPEC] To customize, modify these constants at the top:")
print("[SPEC]   APP_NAME - Executable name")
print("[SPEC]   CONSOLE_MODE - Show console window (True/False)")
print("[SPEC]   OPTIMIZE_LEVEL - Optimization intensity")
print("[SPEC]")
print("[SPEC] To add an icon, uncomment icon line and set path")
print("[SPEC]")
