# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from textwrap import dedent

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_root = Path(SPECPATH)
version_string = os.environ.get("FORTUNA_VERSION", "0.0.0")


def ensure_path(rel_path: str) -> Path:
    target = project_root / rel_path
    if not target.exists():
        raise SystemExit(f"[spec] Required path missing: {target}")
    return target


def include_tree(rel_path: str, target: str, store: list):
    absolute = ensure_path(rel_path)
    store.append((str(absolute), target))
    print(f"[spec] Including {absolute} -> {target}")


def build_version_file(version: str) -> str:
    parts = [int(p) for p in version.split(".") if p.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    parts = parts[:4]
    file_content = dedent(
        f"""
        VSVersionInfo(
          ffi=FixedFileInfo(
            filevers={tuple(parts)},
            prodvers={tuple(parts)},
            mask=0x3f,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0)
          ),
          kids=[
            StringFileInfo([
              StringTable(
                '040904B0',
                [
                  StringStruct('CompanyName', 'Fortuna Development Team'),
                  StringStruct('FileDescription', 'Fortuna Backend Web Service'),
                  StringStruct('FileVersion', '{version}'),
                  StringStruct('InternalName', 'fortuna-backend'),
                  StringStruct('ProductName', 'Fortuna Web Service'),
                  StringStruct('ProductVersion', '{version}')
                ]
              )
            ]),
            VarFileInfo([VarStruct('Translation', [1033, 1200])])
          ]
        )
        """
    ).strip()
    version_dir = project_root / "build" / "pyinstaller"
    version_dir.mkdir(parents=True, exist_ok=True)
    version_file = version_dir / "version-info.txt"
    version_file.write_text(file_content, encoding="utf-8")
    return str(version_file)


datas = []
hiddenimports = set()

include_tree("staging/ui", "ui", datas)
include_tree("python_service/adapters", "adapters", datas)
include_tree("python_service/data", "data", datas)
include_tree("python_service/json", "json", datas)

datas += collect_data_files("uvicorn", includes=["*.html", "*.json"])
datas += collect_data_files("slowapi", includes=["*.json", "*.yaml"])
datas += collect_data_files("structlog", includes=["*.json"])
datas += collect_data_files("certifi")

hiddenimports.update(collect_submodules("python_service"))
hiddenimports.update(
    [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.lifespan.on",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.protocols.websockets.websockets_impl",
        "fastapi.routing",
        "fastapi.middleware.cors",
        "fastapi.middleware.gzip",
        "starlette.staticfiles",
        "starlette.middleware.cors",
        "anyio._backends._asyncio",
        "httpcore",
        "httpx",
        "python_multipart",
        "slowapi",
        "structlog",
        "tenacity",
        "aiosqlite",
        "selectolax",
        "pydantic_core",
        "pydantic_settings.sources",
        "win32timezone",
    ]
)

analysis = Analysis(
    ["python_service/main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=sorted(hiddenimports),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests", "pytest", "web_service"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    [],
    name="fortuna-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version=build_version_file(version_string),
)
