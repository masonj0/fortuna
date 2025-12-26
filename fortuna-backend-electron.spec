# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Fortuna Backend
CORRECTED VERSION: This spec uses the robust 'collect_submodules' technique
to emulate '--collect-all' behavior for problematic packages like tenacity.
"""

import sys
from pathlib import Path

# ============================================================================
# Basic Configuration
# ============================================================================
block_cipher = None
spec_file_dir = Path(SPECPATH).parent.resolve()
hooks_directory = spec_file_dir / 'fortuna-backend-hooks'

print(f"[SPEC] Spec file location: {spec_file_dir}")
print(f"[SPEC] Hooks directory: {hooks_directory}")

# ============================================================================
# Data Files (for non-Python assets)
# ============================================================================
datas = []
frontend_path = spec_file_dir / "web_platform/frontend/out"
if frontend_path.exists():
    datas.append((str(frontend_path), 'ui'))
    print(f"[SPEC] ✅ Frontend bundling enabled: {frontend_path}")
else:
    print(f"[SPEC] ⚠️  Frontend not found, UI will not be bundled: {frontend_path}")

# Add data files from core libraries that are not auto-detected
try:
    from PyInstaller.utils.hooks import collect_data_files
    datas += collect_data_files('starlette')
    datas += collect_data_files('fastapi')
    datas += collect_data_files('certifi')
    datas += collect_data_files('tzdata')
    print("[SPEC] ✅ Collected standard library data files.")
except ImportError:
    print("[SPEC] ⚠️ Could not import 'collect_data_files'. Standard library data may be missing.")

# ============================================================================
# Hidden Imports (The Correct Approach)
# ============================================================================
# 1. Start with a minimal list of imports that analysis might miss.
hidden_imports = [
    'win32timezone',
    'win32ctypes',
    'win32ctypes.core',
    'pywin32',
    'pywintypes',
    'pythoncom',
    'win32serviceutil',
    'win32service',
    'win32event',
    'pydantic_settings.sources', # For .env file support
    'sqlalchemy.dialects.sqlite',
    'aiosqlite',
    'greenlet',
]
print(f"[SPEC] Initial hidden imports: {len(hidden_imports)}")

# 2. Emulate '--collect-all' by using collect_submodules directly in the spec.
#    This is the robust way to handle packages with complex/dynamic imports.
print("[SPEC] Force-collecting submodules for problematic packages...")
try:
    from PyInstaller.utils.hooks import collect_submodules
    problematic_packages = [
        'tenacity',
        'uvicorn',
        'structlog',
        'fastapi',
        'starlette',
        'httpx',
        'redis',
        'slowapi',
        'limits',
    ]

    for package in problematic_packages:
        try:
            collected_modules = collect_submodules(package)
            hidden_imports.extend(collected_modules)
            print(f"[SPEC] ✅ Collected {len(collected_modules)} submodules from '{package}'")
        except Exception as e:
            print(f"[SPEC] ⚠️  Could not collect submodules from '{package}': {e}")

    print(f"[SPEC] ✅ Total hidden imports after collection: {len(hidden_imports)}")

except ImportError:
    print("[SPEC] ⚠️ Could not import 'collect_submodules'. Dynamic collection will be skipped.")

# ============================================================================
# Analysis Configuration
# ============================================================================
a = Analysis(
    ['web_service/backend/main.py'],
    pathex=[str(spec_file_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[str(hooks_directory) if hooks_directory.exists() else ''],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tcl', 'tk', '_tkinter', 'tkinter', 'matplotlib', 'pytest',
        'sphinx', 'IPython', 'jupyter', 'distutils', 'python_service'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fortuna-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='fortuna-backend',
)
