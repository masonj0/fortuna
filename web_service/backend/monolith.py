import sys
import os
import threading
import time
import uvicorn
import webview
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Define the FastAPI app
app = FastAPI(title="Fortuna Monolith")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Attempt to import the main API router
try:
    from web_service.backend.api import router as api_router
    app.include_router(api_router, prefix="/api")
    print("[MONOLITH] ✅ Loaded API routers")
except ImportError as e:
    print(f"[MONOLITH] ⚠️  Could not load API routers: {e}")
    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "monolith_fallback", "error": str(e)}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def start_monolith():
    # Mount the bundled frontend
    static_dir = resource_path("frontend_dist")
    if os.path.exists(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"[MONOLITH] ✅ Serving frontend from {static_dir}")
    else:
        print(f"[MONOLITH] ❌ Frontend dist not found at {static_dir}")

    # --- Graceful Shutdown and Server Logic ---
    port = 8000
    url = f"http://127.0.0.1:{port}"
    destroy_event = threading.Event()

    def run_server():
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
        server = uvicorn.Server(config)

        # This is the key to graceful shutdown
        server.should_exit = lambda: destroy_event.is_set()

        # We need to run the server's own startup/shutdown sequence
        server.run()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    time.sleep(2) # Give the server a moment to start

    # --- pywebview Window ---
    window = webview.create_window('Fortuna Faucet', url, width=1280, height=800)

    # When the window is closed, set the event to trigger server shutdown
    def on_closed():
        print('[MONOLITH] Window closed, shutting down server.')
        destroy_event.set()

    window.events.closed += on_closed

    # This is a blocking call that will run until the window is closed
    webview.start(debug=True) # debug=True is helpful for diagnosing issues

if __name__ == '__main__':
    # This is necessary for PyInstaller on Windows
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()
    start_monolith()
