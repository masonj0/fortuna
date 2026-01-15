# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
from pathlib import Path

block_cipher = None

# Get project root (where spec file lives)
project_root = Path(SPECPATH).parent

# CRITICAL: Verify frontend was built
frontend_out = project_root / 'web_service' / 'frontend' / 'out'
if not frontend_out.exists():
    raise FileNotFoundError(
        f"Frontend 'out' directory not found at {frontend_out}. "
        "Run 'npm run build' in web_service/frontend first!"
    )

if not (frontend_out / 'index.html').exists():
    raise FileNotFoundError(
        f"Frontend build incomplete - index.html not found in {frontend_out}"
    )

print(f"✅ Frontend found at: {frontend_out}")
print(f"   Files: {len(list(frontend_out.rglob('*')))}")

# Define data files with validation
datas = []

# Add backend data directories (create if they don't exist)
for dirname in ['data', 'json', 'adapters']:
    src_path = project_root / 'web_service' / 'backend' / dirname
    if src_path.exists():
        datas.append((str(src_path), dirname))
        print(f"✅ Added {dirname}: {src_path}")
    else:
        print(f"⚠️  Skipping {dirname} (doesn't exist): {src_path}")

# Add icon if it exists
icon_path = project_root / 'assets' / 'icon.ico'
if icon_path.exists():
    datas.append((str(icon_path), 'assets'))
    print(f"✅ Added icon: {icon_path}")
else:
    print(f"⚠️  Icon not found: {icon_path}")

# Add frontend (REQUIRED)
datas.append((str(frontend_out), 'ui'))
print(f"✅ Added frontend UI: {frontend_out}")

hiddenimports = [
    'uvicorn', 'fastapi', 'starlette', 'pydantic', 'structlog',
    'tenacity', 'redis', 'sqlalchemy', 'greenlet', 'win32timezone'
] + collect_submodules('web_service.backend')

a = Analysis(
    [str(project_root / 'web_service' / 'backend' / 'main.py')],
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
    console=True,  # Keep console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

print("\n" + "="*60)
print("✅ SPEC FILE PROCESSING COMPLETE")
print("="*60)
