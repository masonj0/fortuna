"""
PyInstaller hook for uvicorn.

Uvicorn uses dynamic imports via importer.py that PyInstaller cannot automatically
detect. This hook ensures all uvicorn submodules are collected into the bundle.

This is a known issue documented in the PyInstaller community and is the standard
solution used by projects like Datasette.
"""

from PyInstaller.utils.hooks import collect_submodules, get_module_file_attribute

# Collect all uvicorn submodules recursively
hiddenimports = collect_submodules('uvicorn')

# Explicitly add critical submodules that might be missed
# These are the modules uvicorn dynamically imports via importer.py
critical_submodules = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.loops.uvloop',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.config',
    'uvicorn.server',
    'uvicorn.lifespan',
    'uvicorn.importer',
    'uvicorn.middleware',
    'uvicorn.middleware.proxy_headers',
    'uvicorn.middleware.wsgi',
]

# Merge and deduplicate
hiddenimports = list(set(hiddenimports + critical_submodules))
