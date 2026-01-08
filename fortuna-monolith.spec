# -*- mode: python ; coding: utf-8 -*-
"""
Fortuna Universal Monolith Spec
Works for all monolith workflows
FIXED: Includes all dependencies + fallback API mode
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files
import os

block_cipher = None

# ====================================================================
# COLLECT EVERYTHING FROM KEY PACKAGES
# ====================================================================
print("[SPEC] Collecting package data...")

uvicorn_data = collect_all('uvicorn')
fastapi_data = collect_all('fastapi')
starlette_data = collect_all('starlette')
pydantic_data = collect_all('pydantic')
httpx_data = collect_all('httpx')
webview_data = collect_all('webview')

print(f"[SPEC] Uvicorn: {len(uvicorn_data[0])} datas, {len(uvicorn_data[2])} imports")
print(f"[SPEC] FastAPI: {len(fastapi_data[0])} datas, {len(fastapi_data[2])} imports")
print(f"[SPEC] Starlette: {len(starlette_data[0])} datas, {len(starlette_data[2])} imports")

# ====================================================================
# DATA FILES
# ====================================================================
datas = [
    ('frontend_dist', 'frontend_dist'),
]

# Add collected data files
datas += uvicorn_data[0]
datas += fastapi_data[0]
datas += starlette_data[0]
datas += pydantic_data[0]
datas += httpx_data[0]
datas += webview_data[0]

# Backend data directories (if they exist)
backend_data_dirs = [
    ('web_service/backend/data', 'data'),
    ('web_service/backend/json', 'json'),
    ('web_service/backend/adapters', 'adapters'),
    ('web_service/backend/config', 'config'),
    ('web_service/backend/prompts', 'prompts'),
]

for source, dest in backend_data_dirs:
    if os.path.exists(source):
        datas.append((source, dest))
        print(f"[SPEC] Including: {source} -> {dest}")

print(f"[SPEC] Total data files: {len(datas)}")

# ====================================================================
# BINARIES
# ====================================================================
binaries = []
binaries += uvicorn_data[1]
binaries += fastapi_data[1]
binaries += starlette_data[1]
binaries += webview_data[1]

# ====================================================================
# HIDDEN IMPORTS
# ====================================================================
hiddenimports = [
    # Core monolith
    'web_service.backend.monolith',

    # Try to include full API (but monolith works without it)
    'web_service.backend.api',
    'web_service.backend.engine',
    'web_service.backend.cache',
    'web_service.backend.config',

    # Essential HTTP/ASGI
    'h11',
    'httptools',
    'httpcore',
    'anyio._backends._asyncio',

    # Windows
    'win32timezone',
    'win32api',
    'win32con',

    # Logging
    'structlog',
    'logging.config',
]

# Add collected hidden imports
hiddenimports += uvicorn_data[2]
hiddenimports += fastapi_data[2]
hiddenimports += starlette_data[2]
hiddenimports += pydantic_data[2]
hiddenimports += httpx_data[2]
hiddenimports += webview_data[2]

# Collect all submodules (nuclear option)
hiddenimports += collect_submodules('web_service.backend')

# Remove duplicates
hiddenimports = list(set(hiddenimports))
print(f"[SPEC] Total hidden imports: {len(hiddenimports)}")

# ====================================================================
# ANALYSIS
# ====================================================================
a = Analysis(
    ['web_service/backend/monolith.py'],
    pathex=['.'],
    binaries=binaries,
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

# ====================================================================
# EXECUTABLE
# ====================================================================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='fortuna-monolith',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # ENABLE CONSOLE for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # Let it auto-detect (x64 or x86)
    codesign_identity=None,
    entitlements_file=None,
)