# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(SPECPATH).parent
backend_root = project_root / 'web_service' / 'backend'

# Helper function to include data files
def include(rel_path: str, target: str, store: list):
    absolute = backend_root / rel_path
    if absolute.exists():
        store.append((str(absolute), target))
    else:
        print(f"[spec] WARNING: Skipping missing include: {absolute}")

datas = []
hiddenimports = set()

# Include necessary data directories relative to the backend root
include('data', 'data', datas)
include('json', 'json', datas)
include('adapters', 'adapters', datas)

# Automatically collect submodules and data files for key libraries
datas += collect_data_files('uvicorn')
datas += collect_data_files('fastapi')
datas += collect_data_files('starlette')
hiddenimports.update(collect_submodules('web_service.backend'))
hiddenimports.update(collect_submodules('uvicorn'))
hiddenimports.update(collect_submodules('fastapi'))
hiddenimports.update(collect_submodules('starlette'))
hiddenimports.update(collect_submodules('anyio'))
hiddenimports.add('win32timezone')
hiddenimports.update([
    'asyncio',
    'asyncio.windows_events',
    'asyncio.selector_events',
    'pydantic_core',
    'pydantic_settings.sources',
    'httpcore',
    'httpx',
    'python_multipart',
    'numpy',
    'pandas',
    'mss',
    'PIL',
    'cv2',
    'multipart'
])

a = Analysis(
    [str(backend_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=sorted(hiddenimports),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ☢️ PYZ INJECTION: Force __init__ files into the PYZ archive as modules
# This is the definitive fix for ModuleNotFoundError at runtime.
a.pure += [
    ('web_service', str(project_root / 'web_service/__init__.py'), 'PYMODULE'),
    ('web_service.backend', str(backend_root / '__init__.py'), 'PYMODULE'),
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='fortuna-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Set to True for debugging in CI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
