# fortuna-desktop.spec
# This spec file is for creating a windowed, GUI-based application
# using pywebview. It is based on fortuna-monolith.spec.

from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path
import sys
import os

block_cipher = None

# ===== GET PROJECT ROOT =====
spec_path = Path(SPECPATH) if 'SPECPATH' in dir() else Path(os.path.dirname(os.path.abspath(__file__)))
project_root = spec_path.parent if spec_path.name == 'fortuna-desktop.spec' else spec_path

# ===== FRONTEND VALIDATION =====
frontend_out = project_root / 'web_service' / 'frontend' / 'public'
if not frontend_out.exists() or not (frontend_out / 'index.html').exists():
    print("[ERROR] FATAL: Frontend 'public' directory with index.html not found!")
    sys.exit(1)

# ===== BACKEND VALIDATION =====
backend_root = project_root / 'web_service' / 'backend'
main_script = project_root / 'run_desktop_app.py'
if not main_script.exists():
    print(f"[ERROR] FATAL: Main script not found at {main_script}!")
    sys.exit(1)

# ===== DATA FILES =====
datas = [
    (str(frontend_out), 'public')
]

# ===== HIDDEN IMPORTS =====
hiddenimports = list(set(
    collect_submodules('web_service.backend') +
    [
        'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl', 'uvicorn.lifespan', 'uvicorn.lifespan.on',
        'fastapi', 'starlette', 'pydantic', 'anyio', 'structlog', 'tenacity',
        'sqlalchemy', 'greenlet', 'win32timezone',
        'clr', 'win32com', 'win32api', 'win32file'
    ]
))

# ===== ANALYSIS =====
a = Analysis(
    [str(main_script)],
    pathex=[str(project_root), str(backend_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ===== BUILD EXECUTABLE (WINDOWED) =====
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Fortuna-Desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,  # This creates a windowed application
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None # Consider adding an icon here later
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=True,
    name='Fortuna-Desktop'
)
