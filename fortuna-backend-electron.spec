# -*- mode: python ; coding: utf-8 -*-

# To understand PyInstaller spec files, see
# https://pyinstaller.org/en/stable/spec-files.html

import os
import sys
from pathlib import Path

# The path to the repository root directory.
# This is the directory that contains the `electron`, `python_service`, etc. directories.
# When the spec file is executed by PyInstaller, it is done so from the directory that contains the spec file.
# The `fortuna-backend-electron.spec` file is located at the root of the repository.
# So, the current working directory is the repository root.
# For more information, see https://pyinstaller.org/en/stable/spec-files.html#spec-file-operation
root = Path(os.getcwd())
# The path to the `python_service` directory.
python_service = root / 'python_service'
# The path to the main script.
main_script = python_service / 'main.py'

a = Analysis(
    [str(main_script)],
    pathex=[],
    binaries=[],
    datas=[
        (str(python_service / 'data'), 'data'),
        (str(python_service / 'json'), 'json'),
    ],
    hiddenimports=['win32timezone'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fortuna-backend',
)
