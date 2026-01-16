# fortuna-monolith.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path
import sys
import os

block_cipher = None
# Correctly set project_root using the SPECPATH global provided by PyInstaller
project_root = Path(SPECPATH).parent

# ===== FRONTEND VALIDATION =====
frontend_out = project_root / 'web_service' / 'frontend' / 'out'
index_html = frontend_out / 'index.html'

if not index_html.exists():
    print(f"ERROR: Frontend build output not found at {index_html}")
    print(f"   Run: cd web_service/frontend && npm ci && npm run build")
    sys.exit(1)

print(f"OK: Frontend validated: {len(list(frontend_out.rglob('*')))} files")

# ===== BACKEND VALIDATION =====
backend_root = project_root / 'web_service' / 'backend'
main_py = backend_root / 'main.py'

if not main_py.exists():
    print(f"ERROR: Backend main.py not found at {main_py}")
    sys.exit(1)

print(f"OK: Backend validated: main.py found")

# ===== DATA FILES =====
datas = []
datas.append((str(frontend_out), 'ui'))

for dirname in ['data', 'json', 'logs']:
    src = backend_root / dirname
    if src.exists():
        datas.append((str(src), dirname))

# ===== HIDDEN IMPORTS =====
core_imports = [
    'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl', 'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'fastapi', 'fastapi.routing', 'starlette', 'starlette.applications',
    'starlette.routing', 'starlette.responses', 'starlette.staticfiles',
    'pydantic', 'pydantic_core', 'pydantic_settings',
    'anyio', 'structlog', 'tenacity', 'sqlalchemy', 'greenlet', 'win32timezone'
]

backend_submodules = collect_submodules('web_service.backend')
hiddenimports = list(set(core_imports + backend_submodules))

# ===== ANALYSIS =====
a = Analysis(
    [str(main_py)],
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

# ===== BUILD =====
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='fortuna-monolith',
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[],
    runtime_tmpdir=None, console=True,
    disable_windowed_traceback=False,
    target_arch=None, codesign_identity=None,
    entitlements_file=None, icon=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, name='fortuna-monolith'
)
