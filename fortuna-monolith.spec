# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Use __file__ to create absolute paths, making the spec self-contained
SPEC_DIR = Path(__file__).resolve().parent
backend_root = SPEC_DIR / 'web_service' / 'backend'
assets_root = SPEC_DIR / 'assets'
frontend_out = SPEC_DIR / 'web_platform' / 'frontend' / 'out'

# CRITICAL: Bundle the Next.js static frontend using absolute paths
datas = [
    (str(backend_root / 'data'), 'data'),
    (str(backend_root / 'json'), 'json'),
    (str(backend_root / 'adapters'), 'adapters'),
    (str(assets_root / 'icon.ico'), 'assets'),
    (str(frontend_out), 'ui'),
]

hiddenimports = [
    'uvicorn', 'fastapi', 'starlette', 'pydantic', 'structlog',
    'tenacity', 'redis', 'sqlalchemy', 'greenlet', 'win32timezone'
] + collect_submodules('web_service.backend')

a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[str(SPEC_DIR)],
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
