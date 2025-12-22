# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# This spec has been standardized to build the web_service from its own directory,
# removing the dependency on the obsolete 'python_service'.

block_cipher = None
project_root = Path(SPECPATH).parent
backend_root = project_root / 'web_service' / 'backend'

# --- Data Files ---
# Collect all necessary data files from their respective packages.
datas = []
datas += collect_data_files('uvicorn')
datas += collect_data_files('fastapi')
datas += collect_data_files('starlette')

# --- Hidden Imports ---
# Ensure all necessary submodules and dynamically loaded modules are included.
hiddenimports = set()
hiddenimports.update(collect_submodules('web_service.backend'))
hiddenimports.update(collect_submodules('uvicorn'))
hiddenimports.update(collect_submodules('fastapi'))
hiddenimports.update(collect_submodules('starlette'))
hiddenimports.update(collect_submodules('anyio'))
hiddenimports.add('win32timezone') # Critical for Windows service operation
hiddenimports.update(['pydantic_settings.sources']) # For settings management

a = Analysis(
    [str(backend_root / 'service_entry.py')], # Entry point is the service wrapper
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=sorted(hiddenimports),
    hookspath=[],
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
# This creates a single-file executable. The COLLECT object has been removed
# as it is not needed for this build target.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='fortuna-webservice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True # Console is useful for debugging service startup
)
