import sys
import os
import threading
import uvicorn
import webview
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 1. Define the Monolith App
app = FastAPI(title="Fortuna Monolith")

# Allow all origins to prevent CORS issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Robust Router Import
try:
    # Try to import the real API
    from web_service.backend.api import router as api_router
    app.include_router(api_router, prefix="/api")
    print("[MONOLITH] Loaded API routers successfully.")
except Exception as e:
    # If it fails, DO NOT CRASH. Load a fallback route.
    print(f"[MONOLITH] WARNING: Could not load API routers: {e}")
    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "monolith_fallback", "error": str(e)}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def start_monolith():
    # 3. Mount the Frontend (if bundled)
    static_dir = resource_path("frontend_dist")
    if os.path.exists(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"[MONOLITH] Serving frontend from {static_dir}")
    else:
        print(f"[MONOLITH] ERROR: Frontend dist not found at {static_dir}")

    # 4. Start Server & Window
    # Use port 0 to let the OS pick a free port, avoiding conflicts
    port = 8000
    t = threading.Thread(target=uvicorn.run, args=(app,), kwargs={"host": "127.0.0.1", "port": port, "log_level": "info"})
    t.daemon = True
    t.start()

    webview.create_window('Fortuna Faucet', f'http://127.0.0.1:{port}')
    webview.start()

if __name__ == '__main__':
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()
    start_monolith()