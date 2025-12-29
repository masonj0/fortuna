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
# HARDENING REQUIREMENT #3: Absolute Path Logic
# ============================================================================
import os
import sys
from pathlib import Path

# SPECPATH is a variable injected by PyInstaller. It is the reliable way to get the spec file's directory.
# In the CI environment, the project root IS the spec path directory.
project_root = Path(SPECPATH).resolve()

print(f'[SPEC] PyInstaller SPECPATH: {SPECPATH}')
print(f'[SPEC] Project root computed: {project_root}')

# Define all critical paths as absolute
entry_point = project_root / 'web_service' / 'backend' / 'main.py'
frontend_path = project_root / 'web_platform' / 'frontend' / 'out'
hooks_dir = project_root / 'fortuna-backend-hooks'

# Verify paths exist at spec LOAD TIME (not run time)
if not entry_point.exists():
    raise FileNotFoundError(f'Entry point not found: {entry_point}')
if not hooks_dir.exists():
    print(f'[SPEC] WARNING: Hooks directory not found: {hooks_dir}')

print(f'[SPEC] Entry point: {entry_point}')
print(f'[SPEC] Frontend: {frontend_path}')
print(f'[SPEC] Hooks: {hooks_dir}')

# ============================================================================
# Data Files (for non-Python assets)
# ============================================================================
datas = []
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
# HARDCODED CRITICAL HOOKS - Backup to external hook files
# This ensures uvicorn/tenacity/structlog are ALWAYS bundled
# ============================================================================
from PyInstaller.utils.hooks import collect_submodules

print('[SPEC] Applying hardcoded critical hooks for dynamic-import libraries')

# Start with explicit critical list
hardcoded_critical = [
    'tenacity',
    'tenacity.asyncio',
    'tenacity.retry',
    'tenacity.stop',
    'tenacity.wait',
    'uvicorn',
    'uvicorn.config',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.server',
    'structlog',
    'structlog.processors',
]

# BONUS: Try to collect all submodules as additional safety layer
for package in ['tenacity', 'uvicorn', 'structlog']:
    try:
        collected = collect_submodules(package)
        hardcoded_critical.extend(collected)
        print(f'[SPEC] Collected {len(collected)} submodules from {package}')
    except Exception as e:
        print(f'[SPEC] Could not collect from {package}: {e}')

# Deduplicate
hardcoded_critical = list(set(hardcoded_critical))
print(f'[SPEC] Total hardcoded critical imports: {len(hardcoded_critical)}')

# Merge with any existing hidden_imports
hidden_imports = list(set(hidden_imports + hardcoded_critical))
print(f'[SPEC] Final hidden_imports count: {len(hidden_imports)}')

# ============================================================================
# Analysis configuration
# ============================================================================
a = Analysis(
    [str(entry_point)],  # Use absolute path
    pathex=[str(project_root)],  # Use absolute path
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[str(hooks_dir)] if hooks_dir.exists() else [],  # Use absolute path
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
