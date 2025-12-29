# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# This spec has been standardized to build the web_service from its own directory,
# removing the dependency on the obsolete 'python_service'.

block_cipher = None
# Use os.getcwd() for reliable pathing in CI environments
project_root = Path(os.getcwd())
backend_root = project_root / 'web_service' / 'backend'

# --- Data Files ---
# Collect all necessary data files from their respective packages.
datas = []
datas += collect_data_files('uvicorn')
datas += collect_data_files('fastapi')
datas += collect_data_files('starlette')

# --- Hidden Imports ---
# Ensure all necessary submodules and dynamically loaded modules are included.
hiddenimports = []
hiddenimports.extend(collect_submodules('web_service.backend'))
hiddenimports.extend(collect_submodules('uvicorn'))
hiddenimports.extend(collect_submodules('fastapi'))
hiddenimports.extend(collect_submodules('starlette'))
hiddenimports.extend(collect_submodules('anyio'))
hiddenimports.append('win32timezone') # Critical for Windows service operation
hiddenimports.extend(['pydantic_settings.sources']) # For settings management

a = Analysis(
    [str(backend_root / 'service_entry.py')], # Entry point is the service wrapper
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(project_root / 'fortuna-backend-hooks')],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

# --- PYZ Archive ---
# Force __init__.py files into the PYZ archive to ensure robust module loading.
a.pure += [
    ('web_service', str(project_root / 'web_service/__init__.py'), 'PYMODULE'),
    ('web_service.backend', str(backend_root / '__init__.py'), 'PYMODULE'),
]
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- Final Executable ---
# This creates a directory-based ('onedir') build.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fortuna-webservice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

# --- COLLECT Object for Directory-Based Build ---
# This gathers all the dependencies into a single directory, which is the
# standard output for a 'onedir' build.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fortuna-webservice',
)
