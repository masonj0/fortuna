import sys
import os
import threading
import logging
import traceback
from pathlib import Path

# --- 1. SETUP LOGGING (CRITICAL FOR DEBUGGING) ---
def setup_logging():
    # Log to %TEMP% so we can retrieve it if the app crashes
    log_dir = Path(os.environ.get("TEMP", "."))
    log_file = log_dir / "fortuna-desktop.log"

    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='w'
    )

    # Also print to console for dev mode
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(console)
    return logging.getLogger(__name__)

logger = setup_logging()

# --- 2. ROBUST IMPORTS ---
try:
    import uvicorn
    import webview
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
except Exception as e:
    logger.critical(f"Failed to import core dependencies: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# --- 3. DEFINE APP ---
def create_app():
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    # Health Check (Used by CI Smoke Test)
    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "desktop"}

    # Try to load real backend
    try:
        # Lazy import to prevent crash if backend deps are missing
        from web_service.backend.api import router as api_router
        app.include_router(api_router, prefix="/api")
        logger.info("Loaded Backend API")
    except Exception as e:
        logger.warning(f"Could not load Backend API: {e}")
        @app.get("/api/error")
        def api_error(): return {"error": str(e)}

    return app

# --- 4. ASSET PATHS ---
def get_asset_path():
    # PyInstaller unpacks data to _MEIPASS
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / 'public'
    # Dev mode path
    return Path(__file__).parent / 'web_service' / 'frontend' / 'public'

# --- 5. SERVER THREAD ---
def start_server(app, port):
    try:
        # Mount Frontend
        static_dir = get_asset_path()
        if static_dir.exists():
            app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
            logger.info(f"Serving frontend from {static_dir}")
        else:
            logger.error(f"Frontend not found at {static_dir}")

        logger.info(f"Starting Uvicorn on port {port}")
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except Exception as e:
        logger.critical(f"Server crashed: {e}\n{traceback.format_exc()}")

if __name__ == '__main__':
    try:
        if sys.platform == 'win32':
            import multiprocessing
            multiprocessing.freeze_support()

        port = 8000
        app = create_app()

        # Start Backend Thread
        t = threading.Thread(target=start_server, args=(app, port), daemon=True)
        t.start()

        # Start GUI
        logger.info("Launching WebView...")
        webview.create_window("Fortuna Faucet", f"http://127.0.0.1:{port}", width=1280, height=800)
        webview.start()
        logger.info("App closed normally.")

    except Exception as e:
        logger.critical(f"Fatal Crash: {e}\n{traceback.format_exc()}")
        sys.exit(1)