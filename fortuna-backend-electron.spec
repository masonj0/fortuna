# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Fortuna Backend
Final working version with collect_submodules() integration
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ============================================================================
# Spec file directory (Corrected for CI environment)
# ============================================================================
# In a CI environment, SPECPATH can be unreliable. os.getcwd() is more robust.
spec_file_dir = Path(os.getcwd())
hooks_directory = spec_file_dir / 'fortuna-backend-hooks'

print(f"[SPEC] Spec directory: {spec_file_dir}")
print(f"[SPEC] Hooks directory: {hooks_directory}")
print(f"[SPEC] Hooks exist: {Path(hooks_directory).exists()}")

# ============================================================================
# Data Files (for non-Python assets)
# ============================================================================
datas = []
frontend_path = spec_file_dir / "web_platform/frontend/out"
if frontend_path.exists():
    datas.append((str(frontend_path), 'ui'))
    print(f"[SPEC] ✅ Frontend found: {frontend_path}")
else:
    print(f"[SPEC] ⚠️  Frontend not found: {frontend_path}")

# ============================================================================
# Standard data files from packages
# ============================================================================
datas += collect_data_files('starlette')
datas += collect_data_files('fastapi')
datas += collect_data_files('certifi')
datas += collect_data_files('tzdata')

print(f"[SPEC] Data files to include: {len(datas)}")

# ============================================================================
# CRITICAL: Minimal explicit hidden imports
# ============================================================================
# 1. Start with a minimal list of imports that analysis might miss.
hidden_imports = [
    'win32timezone',
    'win32ctypes',
    'win32ctypes.core',
    'pywin32',
    'pywintypes',
    'pythoncom',
]

print(f"[SPEC] Starting with {len(hidden_imports)} explicit hidden imports")

# ============================================================================
# FORCE collect_submodules for problematic packages
# This is the equivalent of --collect-all on the command line
# ============================================================================
print("[SPEC] ========================================")
print("[SPEC] FORCE-COLLECTING SUBMODULES")
print("[SPEC] ========================================")

problematic_packages = [
    ('tenacity', 'Retry library'),
    ('uvicorn', 'ASGI server'),
    ('structlog', 'Logging library'),
    ('fastapi', 'Web framework'),
    ('starlette', 'Web toolkit'),
    ('httpx', 'HTTP client'),
    ('redis', 'Cache client'),
    ('sqlalchemy', 'ORM'),
]
print(f"[SPEC] Initial hidden imports: {len(hidden_imports)}")

for package_name, description in problematic_packages:
    try:
        modules = collect_submodules(package_name)
        hidden_imports.extend(modules)
        print(f"[SPEC] ✅ {package_name:20} -> Collected {len(modules):3} submodules ({description})")
    except Exception as e:
        print(f"[SPEC] ⚠️  {package_name:20} -> Error: {str(e)[:50]}")

print(f"[SPEC] ========================================")
print(f"[SPEC] Total hidden imports: {len(hidden_imports)}")
print(f"[SPEC] ========================================")

# ============================================================================
# Analysis configuration
# ============================================================================
a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[str(spec_file_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[hooks_directory],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tcl', 'tk', '_tkinter', 'tkinter', 'matplotlib', 'pytest',
        'sphinx', 'IPython', 'jupyter', 'distutils', 'python_service'
    ],
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='fortuna-backend',
)
