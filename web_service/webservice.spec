# webservice.spec
from PyInstaller.utils.hooks import collect_data_files
import os

block_cipher = None

# Collect frontend build output
frontend_datas = []
frontend_out = 'web_service/frontend/out'
if os.path.exists(frontend_out):
    frontend_datas = [(frontend_out, 'ui')]

a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web_service/backend/data', 'data'),
        ('web_service/backend/json', 'json'),
        ('python_service', 'python_service'),
        *frontend_datas,
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'numpy',
        'pandas',
    ],
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
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='fortuna-webservice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
