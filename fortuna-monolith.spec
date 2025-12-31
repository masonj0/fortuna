# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None
project_root = Path(SPECPATH).parent
backend_root = project_root / 'web_service' / 'backend'
frontend_dist = project_root / 'web_platform' / 'frontend' / 'out'

datas = []

# 1. Bundle the React Frontend (Must be built first!)
if frontend_dist.exists():
    datas.append((str(frontend_dist), 'frontend_dist'))
else:
    print("WARNING: Frontend dist not found. Run 'npm run build' first!")

# 2. Bundle Backend Assets
for folder in ['data', 'json', 'adapters']:
    source_path = backend_root / folder
    if source_path.exists():
        datas.append((str(source_path), folder))

# 3. Collect Dependencies
hiddenimports = [
    'uvicorn', 'fastapi', 'starlette', 'pydantic', 'structlog',
    'webview', 'webview.platforms.winforms',  # PyWebView dependencies
    'clr',  # Python.NET for Windows Forms
    'playwright', 'playwright.sync_api',  # Playwright for screenshots
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
    icon=None
)