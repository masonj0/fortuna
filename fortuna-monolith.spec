# -*- mode: python ; coding: utf-8 -*-
"""
Fortuna Monolith - PyInstaller Spec
Single executable combining Next.js frontend + FastAPI backend
CRITICAL: Explicit hiddenimports to ensure all modules are bundled
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules
import os
import sys

# ====================================================================
# CONFIGURATION
# ====================================================================
APP_NAME = "fortuna-monolith"
CONSOLE_MODE = True

print("[SPEC] " + "=" * 66)
print(f"[SPEC] Fortuna Monolith PyInstaller Configuration")
print(f"[SPEC] Python: {sys.version.split()[0]}")
print(f"[SPEC] Platform: {sys.platform}")
print("[SPEC] " + "=" * 66)

# ====================================================================
# VERIFY PREREQUISITES
# ====================================================================
prerequisites = {
    'frontend_dist': 'Frontend static files',
    'web_service/backend/monolith.py': 'Monolith entry point',
}

print("[SPEC] Checking prerequisites...")
for path, description in prerequisites.items():
    exists = os.path.exists(path)
    status = "FOUND" if exists else "MISSING"
    print(f"[SPEC]   {description}: {status}")

# ====================================================================
# COLLECT PACKAGE DATA & HOOKS
# ====================================================================
print("[SPEC] Collecting package metadata...")

collected_data = {}
for package in ['uvicorn', 'fastapi', 'starlette', 'pydantic', 'webview']:
    try:
        data = collect_all(package)
        collected_data[package] = data
        print(f"[SPEC]   {package}: OK")
    except Exception as e:
        print(f"[SPEC]   WARNING: {package}: {e}")
        collected_data[package] = ([], [], [])

# ====================================================================
# DATA FILES
# ====================================================================
print("[SPEC] Configuring data files...")
datas = []

if os.path.exists('frontend_dist'):
    datas.append(('frontend_dist', 'frontend_dist'))
    print("[SPEC]   Added: frontend_dist")

for source_dir, dest_dir in [
    ('web_service/backend/data', 'data'),
    ('web_service/backend/json', 'json'),
    ('web_service/backend/logs', 'logs'),
]:
    if os.path.exists(source_dir):
        datas.append((source_dir, dest_dir))

for package, data in collected_data.items():
    datas.extend(data[0])

print(f"[SPEC] Total data files: {len(datas)}")

# ====================================================================
# BINARIES
# ====================================================================
print("[SPEC] Configuring binaries...")
binaries = []
for package, data in collected_data.items():
    binaries.extend(data[1])
print(f"[SPEC] Total binaries: {len(binaries)}")

# ====================================================================
# HIDDEN IMPORTS - CRITICAL FOR PYINSTALLER
# ====================================================================
print("[SPEC] Configuring hidden imports...")

# EXPLICITLY list all modules - do not rely on implicit detection
hiddenimports = [
    # Core application
    'web_service.backend.monolith',

    # FastAPI and web framework - EXPLICIT
    'fastapi',
    'fastapi.openapi',
    'fastapi.openapi.utils',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'fastapi.middleware.base',
    'fastapi.encoders',
    'fastapi.routing',
    'fastapi.security',
    'fastapi.security.utils',
    'fastapi.staticfiles',
    'fastapi.responses',

    # Starlette (ASGI framework) - EXPLICIT
    'starlette',
    'starlette.applications',
    'starlette.authentication',
    'starlette.background',
    'starlette.concurrency',
    'starlette.config',
    'starlette.datastructures',
    'starlette.endpoints',
    'starlette.exceptions',
    'starlette.formparsers',
    'starlette.middleware',
    'starlette.middleware.authentication',
    'starlette.middleware.base',
    'starlette.middleware.cors',
    'starlette.middleware.errors',
    'starlette.middleware.gzip',
    'starlette.middleware.httpsredirect',
    'starlette.middleware.sessions',
    'starlette.middleware.trustedhost',
    'starlette.middleware.wsgi',
    'starlette.responses',
    'starlette.routing',
    'starlette.schemas',
    'starlette.staticfiles',
    'starlette.status',
    'starlette.testclient',
    'starlette.types',
    'starlette.websockets',

    # Uvicorn (ASGI server) - EXPLICIT
    'uvicorn',
    'uvicorn.config',
    'uvicorn.lifespan',
    'uvicorn.lifespan.off',
    'uvicorn.lifespan.on',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.main',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.server',
    'uvicorn.workers',

    # Pydantic (data validation) - EXPLICIT
    'pydantic',
    'pydantic.alias_generators',
    'pydantic.annotated',
    'pydantic.config',
    'pydantic.dataclasses',
    'pydantic.decorator',
    'pydantic.deprecated',
    'pydantic.deprecated.decorator',
    'pydantic.deprecated.json',
    'pydantic.deprecated.tools',
    'pydantic.env_settings',
    'pydantic.fields',
    'pydantic.functional_serializers',
    'pydantic.functional_validators',
    'pydantic.generics',
    'pydantic.json',
    'pydantic.json_schema',
    'pydantic.main',
    'pydantic.networks',
    'pydantic.tools',
    'pydantic.type_adapter',
    'pydantic.types',
    'pydantic.validators',
    'pydantic_core',
    'pydantic_core._pydantic_core',
    'pydantic_settings',

    # HTTP and async - EXPLICIT
    'h11',
    'h2',
    'h2.config',
    'h2.connection',
    'h2.exceptions',
    'h2.stream',
    'httpcore',
    'httpcore._async',
    'httpcore._models',
    'httpcore._sync',
    'httptools',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'anyio._backends._trio',
    'anyio.abc',
    'anyio.streams',

    # WebSockets - EXPLICIT
    'websockets',
    'websockets.client',
    'websockets.frames',
    'websockets.protocol',
    'websockets.server',
    'wsproto',
    'wsproto.connection',
    'wsproto.events',
    'wsproto.extensions',
    'wsproto.frame_builder',
    'wsproto.utilities',

    # GUI - EXPLICIT
    'webview',
    'webview.api',
    'webview.dom',
    'webview.js',
    'webview.menu',
    'webview.window',

    # Windows - EXPLICIT
    'win32timezone',
    'pywin32',
    'win32api',
    'win32con',
    'win32file',

    # Standard library that might be missed - EXPLICIT
    'asyncio',
    'contextvars',
    'dataclasses',
    'decimal',
    'enum',
    'functools',
    'io',
    'itertools',
    'json',
    'logging',
    'logging.config',
    'mimetypes',
    'pathlib',
    'queue',
    're',
    'socket',
    'sqlite3',
    'ssl',
    'stat',
    'string',
    'struct',
    'sys',
    'threading',
    'time',
    'typing',
    'types',
    'urllib',
    'urllib.parse',
    'urllib.request',
    'uuid',
    'warnings',

    # Additional utilities
    'structlog',
    'structlog.stdlib',
    'requests',
    'certifi',
]

# Add collected imports
for package, data in collected_data.items():
    hiddenimports.extend(data[2])

# Try backend submodules
try:
    backend_modules = collect_submodules('web_service.backend')
    hiddenimports.extend(backend_modules)
    print(f"[SPEC] Added {len(backend_modules)} backend submodules")
except:
    pass

# Deduplicate
hiddenimports = list(dict.fromkeys(hiddenimports))
print(f"[SPEC] Total hidden imports: {len(hiddenimports)}")
print(f"[SPEC] CRITICAL: fastapi in hiddenimports: {'fastapi' in hiddenimports}")
print(f"[SPEC] CRITICAL: uvicorn in hiddenimports: {'uvicorn' in hiddenimports}")
print(f"[SPEC] CRITICAL: starlette in hiddenimports: {'starlette' in hiddenimports}")

# ====================================================================
# ANALYSIS
# ====================================================================
print("[SPEC] " + "=" * 66)
print("[SPEC] Running PyInstaller analysis...")
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=CONSOLE_MODE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ====================================================================
# BUILD COMPLETE
# ====================================================================
print("[SPEC] " + "=" * 66)
print("[SPEC] Build configuration complete!")
print("[SPEC] " + "=" * 66)
print(f"[SPEC] Output: dist/{APP_NAME}.exe")
print(f"[SPEC] Hidden imports: {len(hiddenimports)}")
print(f"[SPEC] Verification: fastapi={('fastapi' in hiddenimports)}")
print("[SPEC]")
