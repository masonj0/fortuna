# web_service/backend/monolith.py
import sys
import os
from pathlib import Path
import logging

import io

def _force_utf8_stream(stream):
    """Ensure the given text stream uses UTF-8, even on Windows/CP1252."""
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
        return stream
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream  # Likely already text-only, best effort
    return io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")

def setup_logging():
    log_dir = Path(os.environ.get("TEMP", ".")) if getattr(sys, "frozen", False) else Path(".")
    log_file = log_dir / "fortuna-monolith.log"

    # Force UTF-8 on stdout/stderr to prevent emoji crashes
    stdout = _force_utf8_stream(sys.stdout)
    stderr = _force_utf8_stream(sys.stderr)

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    console_handler = logging.StreamHandler(stdout)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[file_handler, console_handler],
    )
    return logging.getLogger(__name__)

logger = setup_logging()

logger.info("[MONOLITH] Starting up...")
logger.info(f"[MONOLITH] Frozen: {getattr(sys, 'frozen', False)}")
logger.info(f"[MONOLITH] Python: {sys.version}")

try:
    import threading
    import time
    import uvicorn
    import webview
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    logger.info("[MONOLITH] ✅ Core imports successful")
except Exception as e:
    logger.error(f"[MONOLITH] ❌ Import failed: {e}", exc_info=True)
    sys.exit(1)

def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller"""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent
    return base_path / relative_path

def create_minimal_backend_api():
    """
    Create a minimal backend API WITH fallback endpoints if full import fails.
    """
    api = FastAPI(title="Fortuna Backend API")

    # Health endpoint
    @api.get("/health")
    async def health():
        return {"status": "ok", "service": "fortuna-monolith"}

    # Try to import full backend
    try:
        logger.info("[MONOLITH] Attempting to load full backend API...")
        from web_service.backend.api import app as full_backend
        from web_service.backend import races  # Explicit import for /api/races

        # Mount routes from full backend
        for route in full_backend.routes:
            api.routes.append(route)

        # Ensure /api/races is available
        if not any(str(r.path) == "/races" for r in api.routes):
            from web_service.backend.api import router as races_router
            api.include_router(races_router)

        logger.info("[MONOLITH] ✅ Full backend API loaded with races endpoint")
    except ImportError as e:
        logger.warning(f"[MONOLITH] ⚠️ Full backend import failed: {e}. Using minimal API with stubs.")

        # Stub for /api/races (return sample data)
        @api.get("/races")
        async def get_races():
            return [
                {"id": 1, "name": "Sample Race 1", "status": "active"},
                {"id": 2, "name": "Sample Race 2", "status": "completed"}
            ]

        @api.get("/")
        async def root():
            return {"message": "Fortuna Monolith (Minimal Mode)", "error": str(e)}

    return api

def create_app():
    """Create FastAPI app with proper routing for Next.js export"""
    app = FastAPI(title="Fortuna Monolith")

    # CRITICAL: Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create backend API (with fallback to minimal mode)
    logger.info("[MONOLITH] Creating backend API...")
    backend_app = create_minimal_backend_api()

    # Mount backend API FIRST (higher priority)
    app.mount("/api", backend_app, name="backend")
    logger.info("[MONOLITH] ✅ Backend API mounted at /api")

    # Get frontend path
    frontend_path = get_resource_path('frontend_dist')
    logger.info(f"[MONOLITH] Frontend path: {frontend_path}")
    logger.info(f"[MONOLITH] Frontend exists: {frontend_path.exists()}")

    if frontend_path.exists():
        # Check for index.html
        index_file = frontend_path / "index.html"
        if index_file.exists():
            logger.info("[MONOLITH] ✅ Found index.html")
        else:
            logger.warning("[MONOLITH] ⚠️  index.html not found!")
            contents = list(frontend_path.iterdir())[:10]  # First 10 items
            logger.warning(f"[MONOLITH] Contents: {contents}")

        # Mount static assets
        next_dir = frontend_path / "_next"
        if next_dir.exists():
            app.mount("/_next", StaticFiles(directory=str(next_dir)), name="next-static")
            logger.info("[MONOLITH] ✅ Mounted /_next static files")

        # Catch-all route to serve frontend
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            # Skip API routes
            if full_path.startswith("api"):
                return {"error": "Not found"}

            # Try exact file
            file_path = frontend_path / full_path
            if file_path.is_file():
                return FileResponse(file_path)

            # Try with .html
            html_path = frontend_path / f"{full_path}.html"
            if html_path.is_file():
                return FileResponse(html_path)

            # Default to index.html (SPA routing)
            if index_file.exists():
                return FileResponse(index_file)
            else:
                return {
                    "error": "Frontend not properly bundled",
                    "path": str(index_file),
                    "exists": index_file.exists()
                }

        logger.info("[MONOLITH] ✅ Frontend routing configured")
    else:
        logger.error("[MONOLITH] ❌ Frontend files not found!")

        @app.get("/")
        async def root():
            return {
                "error": "Frontend not found",
                "path": str(frontend_path),
                "help": "Frontend was not bundled into the EXE"
            }

    return app

def run_backend():
    """Run backend with comprehensive error handling"""
    try:
        logger.info("[MONOLITH] Creating FastAPI app...")
        app = create_app()

        logger.info("[MONOLITH] Starting Uvicorn on http://127.0.0.1:8000")
        logger.info("[MONOLITH] Press CTRL+C in console to stop")

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        logger.error(f"[MONOLITH] ❌ Backend crashed: {e}", exc_info=True)
        # Don't exit - let main() handle it
        raise

def main():
    """Main entry with comprehensive error handling"""
    try:
        logger.info("[MONOLITH] 🍀 Starting Fortuna Monolith...")
        logger.info(f"[MONOLITH] Working directory: {os.getcwd()}")
        logger.info(f"[MONOLITH] Executable: {sys.executable}")

        # Start backend thread
        logger.info("[MONOLITH] Starting backend thread...")
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        logger.info("[MONOLITH] ✅ Backend thread started")

        # Wait for backend to initialize
        logger.info("[MONOLITH] ⏳ Waiting 5 seconds for backend to start...")
        time.sleep(5)

        # Test backend health
        logger.info("[MONOLITH] Testing backend health...")
        import requests

        backend_healthy = False
        for attempt in range(1, 11):
            try:
                response = requests.get("http://127.0.0.1:8000/api/health", timeout=2)
                status = response.status_code
                logger.info(f"[MONOLITH] Health check attempt {attempt}/10: Status {status}")

                if status == 200:
                    data = response.json()
                    logger.info(f"[MONOLITH] Health response: {data}")
                    backend_healthy = True
                    logger.info("[MONOLITH] ✅ Backend is healthy!")
                    break
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[MONOLITH] Connection error (attempt {attempt}/10): Backend not ready yet")
            except Exception as e:
                logger.warning(f"[MONOLITH] Health check failed (attempt {attempt}/10): {e}")

            time.sleep(1)

        if not backend_healthy:
            logger.error("[MONOLITH] ❌ Backend never became healthy!")
            logger.error("[MONOLITH] The app will still launch but may not work correctly")
            logger.error("[MONOLITH] Check the log file for errors")

        # Launch webview
        logger.info("[MONOLITH] 🚀 Launching webview window...")
        webview.create_window(
            title="Fortuna Faucet",
            url="http://127.0.0.1:8000",
            width=1400,
            height=900,
            resizable=True,
            min_size=(800, 600),
            background_color='#1a1a1a'
        )

        logger.info("[MONOLITH] Starting webview event loop...")
        webview.start(debug=True)

        logger.info("[MONOLITH] 👋 Webview closed, application exiting")

    except Exception as e:
        logger.error(f"[MONOLITH] ❌ Fatal error in main(): {e}", exc_info=True)

        # Show error dialog if possible
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Fortuna Monolith Error",
                f"Application failed to start:\n\n{str(e)}\n\nCheck log at: %TEMP%\\fortuna-monolith.log"
            )
        except:
            pass

        sys.exit(1)

if __name__ == "__main__":
    main()