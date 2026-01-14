# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Get the absolute path of the directory containing this .spec file
basedir = os.path.abspath(os.path.dirname(__file__))

# Define paths relative to the base directory
backend_root = os.path.join(basedir, 'web_service', 'backend')
assets_root = os.path.join(basedir, 'assets')
frontend_out = os.path.join(basedir, 'web_platform', 'frontend', 'out')

# CRITICAL: Bundle the Next.js static frontend using absolute paths
datas = [
    (os.path.join(backend_root, 'data'), 'data'),
    (os.path.join(backend_root, 'json'), 'json'),
    (os.path.join(backend_root, 'adapters'), 'adapters'),
    (os.path.join(assets_root, 'icon.ico'), 'assets'),
    (frontend_out, 'ui'),
]

hiddenimports = [
    'uvicorn', 'fastapi', 'starlette', 'pydantic', 'structlog',
    'tenacity', 'redis', 'sqlalchemy', 'greenlet', 'win32timezone'
] + collect_submodules('web_service.backend')

a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name='fortuna-monolith',
    debug=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version='file_version_info.txt'
)
