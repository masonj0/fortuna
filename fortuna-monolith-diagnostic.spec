# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all
from pathlib import Path
import sys

print("\n" + "="*70)
print("PYINSTALLER SPEC FILE EXECUTION - DIAGNOSTIC MODE")
print("="*70)

block_cipher = None

# Get project root
project_root = Path(SPECPATH).parent
print(f"\n📁 Project Root: {project_root}")
print(f"   Spec Path: {SPECPATH}")
print(f"   Current Dir: {Path.cwd()}")

# ========== STEP 1: LOCATE FRONTEND ==========
print("\n" + "="*70)
print("STEP 1: LOCATING FRONTEND")
print("="*70)

frontend_search_paths = [
    project_root / 'web_platform' / 'frontend' / 'out',
    project_root / 'web_service' / 'frontend' / 'out',
    project_root / 'frontend' / 'out',
]

frontend_out = None
for path in frontend_search_paths:
    print(f"Checking: {path}")
    if path.exists():
        frontend_out = path
        print(f"✅ FOUND: {path}")
        break
    else:
        print(f"❌ Not found: {path}")

if not frontend_out:
    print("\n🚨 CRITICAL ERROR: Frontend 'out' directory not found!")
    print("Searched in:")
    for path in frontend_search_paths:
        print(f"  - {path}")
    sys.exit(1)

# Verify frontend has content
index_html = frontend_out / 'index.html'
if not index_html.exists():
    print(f"\n🚨 CRITICAL ERROR: index.html not found at {index_html}")
    sys.exit(1)

frontend_files = list(frontend_out.rglob('*'))
print(f"✅ Frontend validated: {len(frontend_files)} files")
print(f"   index.html: {index_html.stat().st_size} bytes")

# ========== STEP 2: LOCATE BACKEND ==========
print("\n" + "="*70)
print("STEP 2: LOCATING BACKEND")
print("="*70)

backend_search_paths = [
    project_root / 'web_service' / 'backend',
    project_root / 'python_service',
    project_root / 'backend',
]

backend_root = None
for path in backend_search_paths:
    main_py = path / 'main.py'
    print(f"Checking: {main_py}")
    if main_py.exists():
        backend_root = path
        print(f"✅ FOUND: {backend_root}")
        break
    else:
        print(f"❌ Not found: {path}")

if not backend_root:
    print("\n🚨 CRITICAL ERROR: Backend main.py not found!")
    sys.exit(1)

main_py_path = backend_root / 'main.py'
print(f"✅ Backend entry point: {main_py_path}")
print(f"   Size: {main_py_path.stat().st_size} bytes")

# ========== STEP 3: COLLECT DATA FILES ==========
print("\n" + "="*70)
print("STEP 3: COLLECTING DATA FILES")
print("="*70)

datas = []

# Add frontend (CRITICAL)
datas.append((str(frontend_out), 'ui'))
print(f"✅ Added frontend: {frontend_out} -> ui/")

# Add backend data directories (optional)
for dirname in ['data', 'json', 'adapters']:
    src_path = backend_root / dirname
    if src_path.exists():
        datas.append((str(src_path), dirname))
        print(f"✅ Added {dirname}: {src_path}")
    else:
        print(f"⚠️  Skipping {dirname} (doesn't exist): {src_path}")

# Add icon (optional)
icon_path = project_root / 'assets' / 'icon.ico'
if icon_path.exists():
    datas.append((str(icon_path), 'assets'))
    print(f"✅ Added icon: {icon_path}")
else:
    print(f"⚠️  Icon not found (will use default): {icon_path}")

# ========== STEP 4: HIDDEN IMPORTS ==========
print("\n" + "="*70)
print("STEP 4: COLLECTING HIDDEN IMPORTS")
print("="*70)

# Core dependencies
core_imports = [
    'uvicorn',
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
    'structlog',
    'tenacity',
    'win32timezone',
    'sqlalchemy',
    'greenlet',
]

print("Core imports:")
for imp in core_imports:
    print(f"  - {imp}")

# Collect all submodules from backend
print(f"\nCollecting submodules from: web_service.backend")
backend_submodules = collect_submodules('web_service.backend')
print(f"✅ Found {len(backend_submodules)} submodules")

# Collect all data files from key packages
print("\nCollecting data files from packages:")
for pkg in ['uvicorn', 'fastapi', 'starlette']:
    try:
        pkg_datas = collect_data_files(pkg)
        if pkg_datas:
            datas.extend(pkg_datas)
            print(f"✅ {pkg}: {len(pkg_datas)} data files")
    except Exception as e:
        print(f"⚠️  {pkg}: {e}")

hiddenimports = list(set(core_imports + backend_submodules))
print(f"\n✅ Total hidden imports: {len(hiddenimports)}")

# ========== STEP 5: ANALYSIS ==========
print("\n" + "="*70)
print("STEP 5: CREATING ANALYSIS")
print("="*70)

a = Analysis(
    [str(main_py_path)],
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

print("✅ Analysis created")
print(f"   Scripts: {len(a.scripts)}")
print(f"   Pure modules: {len(a.pure)}")
print(f"   Binaries: {len(a.binaries)}")
print(f"   Data files: {len(a.datas)}")

# ========== STEP 6: PYZ ARCHIVE ==========
print("\n" + "="*70)
print("STEP 6: CREATING PYZ ARCHIVE")
print("="*70)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
print("✅ PYZ archive created")

# ========== STEP 7: EXECUTABLE ==========
print("\n" + "="*70)
print("STEP 7: CREATING EXECUTABLE")
print("="*70)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='fortuna-monolith',
    debug=True,  # Enable debug mode
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

print("✅ Executable configuration created")
print("\n" + "="*70)
print("SPEC FILE EXECUTION COMPLETE")
print("="*70 + "\n")
