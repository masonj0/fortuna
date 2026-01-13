# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = Path(SPECPATH).parent
backend_root = project_root / 'web_service' / 'backend'

# CRITICAL: Bundle the Next.js static frontend
datas = [
    (str(backend_root / 'data'), 'data'),
    (str(backend_root / 'json'), 'json'),
    (str(backend_root / 'adapters'), 'adapters'),
    (str(project_root / 'assets' / 'icon.ico'), 'assets'),
    # THE KEY: Frontend static export bundled into executable
    (str(project_root / 'web_platform' / 'frontend' / 'out'), 'ui'),
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
