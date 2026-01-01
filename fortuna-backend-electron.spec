# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(SPECPATH).parent
# FIXED: Target the consolidated backend
backend_root = project_root / 'web_service' / 'backend'

# Collect data folders
datas = []
for folder in ['data', 'json', 'adapters']:
    source_path = backend_root / folder
    if source_path.exists():
        datas.append((str(source_path), folder))

# Collect dependencies
hiddenimports = [
    'uvicorn', 'fastapi', 'starlette', 'pydantic', 'structlog',
    'tenacity', 'redis', 'sqlalchemy', 'greenlet', 'win32timezone'
] + collect_submodules('web_service.backend')

a = Analysis(
    ['web_service/backend/main.py'], # FIXED: Entry point
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
    name='fortuna-backend',
    debug=False,
    strip=False,
    upx=True,
    console=True, # Keep console for Electron backend debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
