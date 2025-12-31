import sys
import os
import threading
import uvicorn
import webview  # pip install pywebview
from fastapi.staticfiles import StaticFiles

# Import the existing backend logic
from web_service.backend.main import app

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def start_monolith():
    # 1. Mount the bundled Frontend (built by React)
    # We expect the 'frontend_dist' folder to be bundled inside the EXE
    static_dir = resource_path("frontend_dist")
    if os.path.exists(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"[MONOLITH] Serving frontend from {static_dir}")
    else:
        print("[MONOLITH] WARNING: Frontend dist not found. API only mode.")

    # 2. Start the Server in a background thread
    # We bind to localhost on a random free port (0) or fixed port
    port = 8000
    t = threading.Thread(target=uvicorn.run, args=(app,), kwargs={"host": "127.0.0.1", "port": port, "log_level": "error"})
    t.daemon = True
    t.start()

    # 3. Launch the Native Window
    # This replaces the Electron shell
    webview.create_window('Fortuna Faucet (Monolith)', f'http://127.0.0.1:{port}')
    webview.start()

if __name__ == '__main__':
    # Ensure PyInstaller multiprocessing works
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()

    start_monolith()