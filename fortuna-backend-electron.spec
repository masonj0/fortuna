# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Fortuna Backend - FIXED VERSION
This spec properly references the custom hooks directory for uvicorn bundling.
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# ============================================================================
# CRITICAL: Determine hooks directory relative to spec file location
# ============================================================================
# Use SPECPATH, the PyInstaller-provided global containing the path to the spec file.
spec_file_dir = Path(SPECPATH).parent.resolve()
hooks_directory = str(spec_file_dir / 'fortuna-backend-hooks')

print(f"[SPEC] Spec file location: {spec_file_dir}")
print(f"[SPEC] Hooks directory: {hooks_directory}")

if not Path(hooks_directory).exists():
    print(f"[SPEC] ⚠️  WARNING: Hooks directory does not exist: {hooks_directory}")
else:
    print(f"[SPEC] ✅ Hooks directory found")

# ============================================================================
# Frontend data bundling
# ============================================================================
frontend_path = spec_file_dir / "web_platform/frontend/out"
datas = []

if frontend_path.exists():
    datas.append((str(frontend_path), 'ui'))
    print(f"[SPEC] ✅ Frontend bundling enabled: {frontend_path}")
else:
    print(f"[SPEC] ⚠️  Frontend not found: {frontend_path}")

# ============================================================================
# Additional data files from packages
# ============================================================================
datas += collect_data_files('starlette')
datas += collect_data_files('fastapi')
datas += collect_data_files('certifi')
datas += collect_data_files('tzdata')

# ============================================================================
# CRITICAL: Hidden imports - explicit list for PyInstaller
# ============================================================================
hidden_imports = [
    # Windows service support
    'win32timezone',
    'win32serviceutil',
    'win32service',
    'win32event',

    # Web framework core
    'fastapi',
    'fastapi.openapi',
    'fastapi.openapi.models',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.routing',
    'starlette.responses',
    'starlette.staticfiles',
    'starlette.websockets',

    # Uvicorn (CRITICAL - even with hook, explicit listing helps)
    'uvicorn',
    'uvicorn.config',
    'uvicorn.server',
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
    'uvicorn.lifespan',
    'uvicorn.importer',

    # Pydantic
    'pydantic',
    'pydantic.json',
    'pydantic_settings',
    'pydantic_core',

    # Structlog (CRITICAL - was missing)
    'structlog',
    'structlog.processors',
    'structlog.testing',

    # SQLAlchemy
    'sqlalchemy',
    'sqlalchemy.orm',
    'sqlalchemy.dialects',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.postgresql',
    'aiosqlite',
    'greenlet',

    # HTTP clients
    'httpx',
    'httpx._models',
    'httpx._client',
    'httpcore',

    # Redis
    'redis',
    'redis.asyncio',

    # Rate limiting
    'slowapi',
    'limits',
    'tenacity',

    # Data processing
    'numpy',
    'pandas',
    'scipy',

    # HTML parsing
    'beautifulsoup4',
    'selectolax',

    # Image processing
    'PIL',
    'cv2',
    'mss',

    # Utilities
    'pytz',
    'python_dateutil',
    'cryptography',
    'certifi',
    'dotenv',
    'click',
]

# ============================================================================
# Analysis configuration
# ============================================================================
a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[str(spec_file_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    # ✅ CRITICAL FIX: Explicitly specify hooks directory
    hookspath=[hooks_directory],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tcl',
        'tk',
        '_tkinter',
        'tkinter',
        'matplotlib',
        'pytest',
        'sphinx',
        'IPython',
        'jupyter',
        'distutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ============================================================================
# PYZ (Python archive)
# ============================================================================
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# ============================================================================
# EXE (Executable)
# ============================================================================
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
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ============================================================================
# COLLECT (Final bundle)
# ============================================================================
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
