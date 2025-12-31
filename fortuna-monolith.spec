# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Use absolute paths to avoid confusion
project_root = Path(os.getcwd()).absolute()
backend_root = project_root / 'web_service' / 'backend'
frontend_dist = project_root / 'web_platform' / 'frontend' / 'out'

print(f"[SPEC] Project Root: {project_root}")
print(f"[SPEC] Frontend Dist: {frontend_dist}")

datas = []

# 1. Bundle Frontend
if frontend_dist.exists():
    datas.append((str(frontend_dist), 'frontend_dist'))
    print("[SPEC] Added frontend_dist")
else:
    print("[SPEC] ❌ WARNING: Frontend dist NOT found at expected path!")

# 2. Bundle Backend Assets
for folder in ['data', 'json', 'adapters']:
    source_path = backend_root / folder
    if source_path.exists():
        datas.append((str(source_path), folder))

# 3. Dependencies
hiddenimports = [
    'uvicorn', 'fastapi', 'starlette', 'pydantic', 'structlog',
    'webview', 'webview.platforms.winforms', 'clr',
    'tenacity', 'redis', 'sqlalchemy', 'greenlet',
    'playwright', 'playwright.sync_api'
] + collect_submodules('web_service.backend')

a = Analysis(
    ['web_service/backend/monolith.py'],
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
    name='FortunaMonolith',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)