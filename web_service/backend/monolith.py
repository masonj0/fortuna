import sys
import os
import threading
import uvicorn
import webview  # PyWebView (The lightweight browser wrapper)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 1. Setup the App
app = FastAPI(title="Fortuna Monolith")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 2. Import your existing API logic
try:
    from web_service.backend.api import router as api_router
    app.include_router(api_router, prefix="/api")
except Exception as e:
    print(f"[MONOLITH] Warning: API router not found ({e}). Running in UI-only mode.")

# 3. The Magic: Serve the Frontend from INSIDE the EXE
def get_asset_path():
    """ Returns the path to the bundled frontend assets """
    if hasattr(sys, '_MEIPASS'):
        # Running as a PyInstaller EXE
        return os.path.join(sys._MEIPASS, "frontend_dist")
    else:
        # Running as a script (Dev mode)
        return os.path.join(os.path.abspath("."), "frontend_dist")

static_dir = get_asset_path()

if os.path.exists(static_dir):
    # Serve the React App at the root URL
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    print(f"[MONOLITH] Serving UI from: {static_dir}")
else:
    print(f"[MONOLITH] UI not found at {static_dir}. API only.")

# 4. Launch Logic
def start_server():
    # Run Uvicorn on a specific port
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

if __name__ == '__main__':
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()

    # Start Backend in Thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # Start Frontend Window (Native)
    webview.create_window("Fortuna Faucet", "http://127.0.0.1:8000", width=1200, height=800)
    webview.start()
