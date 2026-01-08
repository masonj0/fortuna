# minimal-monolith.spec
from PyInstaller.utils.hooks import collect_all

# Collect EVERYTHING from key packages
uvicorn_all = collect_all('uvicorn')
fastapi_all = collect_all('fastapi')
starlette_all = collect_all('starlette')
webview_all = collect_all('webview')

a = Analysis(
    ['web_service/backend/monolith.py'],
    pathex=[],
    binaries=uvicorn_all[1] + fastapi_all[1] + starlette_all[1] + webview_all[1],
    datas=[('frontend_dist', 'frontend_dist')] + uvicorn_all[0] + fastapi_all[0] + starlette_all[0] + webview_all[0],
    hiddenimports=uvicorn_all[2] + fastapi_all[2] + starlette_all[2] + webview_all[2] + [
        'web_service.backend.api',
        'h11', 'httptools', 'httpx', 'anyio'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='fortuna-monolith',
    debug=False,
    console=True,  # ENABLE CONSOLE
    upx=True,
)
