# ============================================================================
# FILE: fortuna-backend-electron.spec
# FIXED: Includes ALL dependencies including structlog
# ============================================================================

import sys
import os
import pathlib
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Determine the absolute path to the hooks directory
# SPECPATH is a global provided by PyInstaller that contains its own path
spec_dir = pathlib.Path(SPECPATH).parent.resolve()
hooks_dir = str(spec_dir / 'fortuna-backend-hooks')

block_cipher = None

# Let PyInstaller's hooks do the heavy lifting. We only need to specify
# a few known problematic imports here. `win32timezone` is critical for
# pywin32-based services.
hidden_imports = [
    'win32timezone',
]

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
    hookspath=[hooks_dir],
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
