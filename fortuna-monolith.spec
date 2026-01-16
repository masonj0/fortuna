# fortuna-monolith.spec
# FIXED: Proper path resolution for Windows

from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path
import sys
import os

block_cipher = None

# ===== GET PROJECT ROOT =====
# SPECPATH is provided by PyInstaller - it's the directory containing THIS spec file
spec_path = Path(SPECPATH) if 'SPECPATH' in dir() else Path(os.path.dirname(os.path.abspath(__file__)))
project_root = spec_path.parent if spec_path.name == 'fortuna-monolith.spec' else spec_path

print(f"\n{'='*70}")
print(f"FORTUNA MONOLITH SPEC - PATH RESOLUTION")
print(f"{'='*70}")
print(f"Spec file location: {spec_path}")
print(f"Project root:       {project_root}")
print(f"Current working:    {Path.cwd()}")

# ===== FRONTEND VALIDATION =====
print(f"\n{'='*70}")
print(f"FRONTEND VALIDATION")
print(f"{'='*70}")

frontend_out = project_root / 'web_service' / 'frontend' / 'out'
print(f"Looking for frontend at: {frontend_out}")
print(f"Exists: {frontend_out.exists()}")

if frontend_out.exists():
    index_html = frontend_out / 'index.html'
    print(f"index.html path:    {index_html}")
    print(f"index.html exists:  {index_html.exists()}")

    if index_html.exists():
        file_count = len(list(frontend_out.rglob('*')))
        size = index_html.stat().st_size
        print(f"✅ Frontend validated!")
        print(f"   Files: {file_count}")
        print(f"   index.html size: {size} bytes")
    else:
        print(f"❌ FATAL: index.html not found at {index_html}")
        # List what IS in the directory
        print(f"\nContents of {frontend_out}:")
        for item in frontend_out.iterdir():
            print(f"  - {item.name}")
        sys.exit(1)
else:
    print(f"❌ FATAL: Frontend 'out' directory not found!")
    print(f"\nSearching for 'out' directory from project root:")
    for root, dirs, files in os.walk(project_root):
        if 'out' in dirs:
            out_path = Path(root) / 'out'
            print(f"  Found at: {out_path}")
            if (out_path / 'index.html').exists():
                print(f"    ✓ Has index.html")
                frontend_out = out_path
                break
    else:
        print(f"  Not found anywhere!")
        sys.exit(1)

# ===== BACKEND VALIDATION =====
print(f"\n{'='*70}")
print(f"BACKEND VALIDATION")
print(f"{'='*70}")

backend_root = project_root / 'web_service' / 'backend'
main_py = backend_root / 'main.py'

print(f"Looking for backend at: {backend_root}")
print(f"main.py path:           {main_py}")
print(f"main.py exists:         {main_py.exists()}")

if not main_py.exists():
    print(f"❌ FATAL: Backend main.py not found!")
    print(f"\nContents of {backend_root}:")
    if backend_root.exists():
        for item in backend_root.iterdir():
            print(f"  - {item.name}")
    else:
        print(f"  Directory doesn't exist!")
    sys.exit(1)

print(f"✅ Backend validated!")
print(f"   main.py size: {main_py.stat().st_size} bytes")

# ===== DATA FILES =====
print(f"\n{'='*70}")
print(f"COLLECTING DATA FILES")
print(f"{'='*70}")

datas = []

# Frontend
datas.append((str(frontend_out), 'ui'))
print(f"✅ Frontend:  {frontend_out} → ui/")

# Backend directories
for dirname in ['data', 'json', 'logs']:
    src = backend_root / dirname
    if src.exists():
        datas.append((str(src), dirname))
        print(f"✅ {dirname:8}: {src}")
    else:
        print(f"⚠️  {dirname:8}: Not found (will create)")

print(f"\nTotal data entries: {len(datas)}")

# ===== HIDDEN IMPORTS =====
print(f"\n{'='*70}")
print(f"COLLECTING HIDDEN IMPORTS")
print(f"{'='*70}")

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

print(f"Core imports:           {len(core_imports)}")
print(f"Backend submodules:     {len(backend_submodules)}")
print(f"Total hidden imports:   {len(hiddenimports)}")

# ===== ANALYSIS =====
print(f"\n{'='*70}")
print(f"CREATING PYINSTALLER ANALYSIS")
print(f"{'='*70}")

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

print(f"✅ Analysis created")
print(f"   Scripts:       {len(a.scripts)}")
print(f"   Pure modules:  {len(a.pure)}")
print(f"   Binaries:      {len(a.binaries)}")
print(f"   Data files:    {len(a.datas)}")

# ===== BUILD =====
print(f"\n{'='*70}")
print(f"BUILDING EXECUTABLE")
print(f"{'='*70}")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='fortuna-monolith',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=True,
    name='fortuna-monolith'
)

print(f"✅ Spec file complete!")
print(f"\n{'='*70}\n")
