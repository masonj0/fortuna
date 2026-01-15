# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all
from pathlib import Path
import sys

print("\n" + "="*70)
print("FORTUNA MONOLITH - PYINSTALLER SPEC")
print("="*70)

block_cipher = None

# Get project root (where spec file lives)
project_root = Path(SPECPATH).parent
print(f"\n📁 Project Root: {project_root}")

# ========== FRONTEND VALIDATION ==========
print("\n" + "="*70)
print("VALIDATING FRONTEND")
print("="*70)

# THE FIX: Use web_service/frontend (not web_platform)
frontend_out = project_root / 'web_service' / 'frontend' / 'out'

if not frontend_out.exists():
    print(f"\n🚨 CRITICAL ERROR: Frontend 'out' directory not found!")
    print(f"   Expected at: {frontend_out}")
    print(f"\n   Did you run 'npm run build' in web_service/frontend?")
    print(f"   Does web_service/frontend/next.config.js have 'output: export'?")
    sys.exit(1)

index_html = frontend_out / 'index.html'
if not index_html.exists():
    print(f"\n🚨 CRITICAL ERROR: index.html not found!")
    print(f"   Expected at: {index_html}")
    sys.exit(1)

frontend_files = list(frontend_out.rglob('*'))
print(f"✅ Frontend validated")
print(f"   Location: {frontend_out}")
print(f"   Files: {len(frontend_files)}")
print(f"   index.html: {index_html.stat().st_size} bytes")

# ========== BACKEND VALIDATION ==========
print("\n" + "="*70)
print("VALIDATING BACKEND")
print("="*70)

backend_root = project_root / 'web_service' / 'backend'
main_py = backend_root / 'main.py'

if not main_py.exists():
    print(f"\n🚨 CRITICAL ERROR: Backend main.py not found!")
    print(f"   Expected at: {main_py}")
    sys.exit(1)

print(f"✅ Backend validated")
print(f"   main.py: {main_py}")
print(f"   Size: {main_py.stat().st_size} bytes")

# ========== DATA FILES ==========
print("\n" + "="*70)
print("COLLECTING DATA FILES")
print("="*70)

datas = []

# Add frontend (CRITICAL)
datas.append((str(frontend_out), 'ui'))
print(f"✅ Frontend: {frontend_out} -> ui/")

# Add backend data directories (create if missing)
for dirname in ['data', 'json', 'adapters']:
    src_path = backend_root / dirname
    if src_path.exists():
        datas.append((str(src_path), dirname))
        print(f"✅ {dirname}: {src_path}")
    else:
        print(f"⚠️  {dirname}: Not found (will skip)")

# Add icon (optional)
icon_path = project_root / 'assets' / 'icon.ico'
if icon_path.exists():
    datas.append((str(icon_path), 'assets'))
    print(f"✅ Icon: {icon_path}")
else:
    icon_path = None
    print(f"⚠️  Icon not found (will use default)")

# Collect data files from key packages
print("\nCollecting package data files...")
for pkg in ['uvicorn', 'fastapi', 'starlette']:
    try:
        pkg_datas = collect_data_files(pkg)
        if pkg_datas:
            datas.extend(pkg_datas)
            print(f"✅ {pkg}: {len(pkg_datas)} files")
    except Exception as e:
        print(f"⚠️  {pkg}: {e}")

# ========== HIDDEN IMPORTS ==========
print("\n" + "="*70)
print("COLLECTING HIDDEN IMPORTS")
print("="*70)

# Core FastAPI/Uvicorn imports
core_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.routing',
    'starlette',
    'starlette.applications',
    'starlette.routing',
    'starlette.responses',
    'starlette.staticfiles',
    'pydantic',
    'pydantic_core',
    'pydantic_settings',
    'anyio',
    'structlog',
    'tenacity',
    'sqlalchemy',
    'greenlet',
    'win32timezone',
]

# Collect backend submodules
backend_submodules = collect_submodules('web_service.backend')
print(f"✅ Backend submodules: {len(backend_submodules)}")

hiddenimports = list(set(core_imports + backend_submodules))
print(f"✅ Total hidden imports: {len(hiddenimports)}")

# ========== ANALYSIS ==========
print("\n" + "="*70)
print("CREATING ANALYSIS")
print("="*70)

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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

print(f"✅ Analysis complete")
print(f"   Scripts: {len(a.scripts)}")
print(f"   Pure modules: {len(a.pure)}")
print(f"   Binaries: {len(a.binaries)}")
print(f"   Data files: {len(a.datas)}")

# ========== PYZ & EXE ==========
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='fortuna-monolith',
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
    icon=str(icon_path) if icon_path else None,
)

print("\n" + "="*70)
print("✅ SPEC FILE COMPLETE")
print("="*70 + "\n")