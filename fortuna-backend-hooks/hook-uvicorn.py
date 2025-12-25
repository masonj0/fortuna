# fortuna-backend-hooks/hook-uvicorn.py
"""
Hook for uvicorn to ensure all submodules are bundled.
Uvicorn uses dynamic imports that PyInstaller cannot automatically detect.
"""

from PyInstaller.utils.hooks import collect_submodules

# Collect ALL uvicorn submodules
hiddenimports = collect_submodules('uvicorn')

# Explicitly add critical submodules if collect_submodules misses them
explicit_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.config',
    'uvicorn.server',
    'uvicorn.lifespan',
    'uvicorn.importer',
]

# Merge both lists, removing duplicates
hiddenimports = list(set(hiddenimports + explicit_imports))
