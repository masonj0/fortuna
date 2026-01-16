# fortuna-monolith.spec
import sys
import os
from pathlib import Path

# ================= BEGIN DIAGNOSTIC SCRIPT =================
# This script runs before the spec is parsed. Its purpose is to
# give us a ground-truth look at the filesystem from Python's perspective
# at the exact moment PyInstaller starts.

print("--- [DIAGNOSTIC] Python and OS Info ---")
print(f"Python Version: {sys.version}")
print(f"OS Platform: {sys.platform}")
print(f"Current Working Dir: {os.getcwd()}")
print("--- [END DIAGNOSTIC] ---")

# In PyInstaller, SPECPATH is the absolute path to this .spec file.
# We use it to derive the project root, which is its parent directory.
spec_path = Path(SPECPATH)
project_root_diag = spec_path.parent
print(f"--- [DIAGNOSTIC] Project Root (derived from SPECPATH): {project_root_diag} ---")

def log_tree(start_path):
    """Recursively logs the contents of a directory."""
    print(f"\n--- [DIAGNOSTIC] Recursive directory listing for: {start_path} ---")
    if not start_path.is_dir():
        print(f"ERROR: Path is not a directory or does not exist.")
        return

    file_count = 0
    dir_count = 0

    for root, dirs, files in os.walk(str(start_path)):
        level = root.replace(str(start_path), '').count(os.sep)
        indent = ' ' * 4 * (level)
        print(f'{indent}{os.path.basename(root)}/')
        sub_indent = ' ' * 4 * (level + 1)
        for d in sorted(dirs):
            dir_count += 1
            print(f'{sub_indent}DIR: {d}')
        for f in sorted(files):
            file_count += 1
            try:
                # Get file size, handle potential errors
                file_path = Path(root) / f
                size_bytes = file_path.stat().st_size
                print(f'{sub_indent}FILE: {f} ({size_bytes} bytes)')
            except OSError as e:
                print(f'{sub_indent}FILE: {f} (Error getting size: {e})')

    print(f"--- [END DIAGNOSTIC] Found {file_count} files and {dir_count} directories. ---")

# Run the diagnostic listing on the entire project root.
# This will show us EVERYTHING the script can see.
log_tree(project_root_diag)

# Also, specifically check the path to the frontend build output
frontend_out_diag = project_root_diag / 'web_service' / 'frontend' / 'out'
log_tree(frontend_out_diag)
print("--- [DIAGNOSTIC] End of pre-flight checks. Spec parsing will now begin. ---\n")
# ================= END DIAGNOSTIC SCRIPT =================


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
