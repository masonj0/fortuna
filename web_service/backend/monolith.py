# web_service/backend/monolith.py
"""
Fortuna Monolith - Single executable frontend + backend
Includes comprehensive error handling and fallback modes
"""
import sys
import os
from pathlib import Path
import logging
import io

# ====================================================================
# SETUP LOGGING (BEFORE ANYTHING ELSE)
# ====================================================================
def _force_utf8_stream(stream):
    """Ensure text stream uses UTF-8 (prevents emoji crashes on Windows)"""
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
            return stream
        except:
            pass

    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream

    try:
        return io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
    except:
        return stream

def setup_logging():
    """Setup logging to file + console"""
    # Log to %TEMP% on frozen, current dir in dev
    if getattr(sys, "frozen", False):
        log_dir = Path(os.environ.get("TEMP", "."))
    else:
        log_dir = Path(".")

    log_file = log_dir / "fortuna-monolith.log"

    # Force UTF-8 output
    sys.stdout = _force_utf8_stream(sys.stdout)
    sys.stderr = _force_utf8_stream(sys.stderr)

    # Setup handlers
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, console_handler],
    )

    logger = logging.getLogger("fortuna-monolith")
    return logger

logger = setup_logging()

logger.info("=" * 70)
logger.info("FORTUNA MONOLITH STARTUP")
logger.info("=" * 70)
logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
logger.info(f"Python: {sys.version}")
logger.info(f"Executable: {sys.executable}")
logger.info(f"Working Dir: {os.getcwd()}")

# ====================================================================
# IMPORT CORE DEPENDENCIES
# ====================================================================
try:
    import threading
    import time
    import json
    import requests

    logger.info("✓ Standard library imports successful")
except Exception as e:
    logger.critical(f"✗ Failed to import standard library: {e}", exc_info=True)
    sys.exit(1)

try:
    import uvicorn
    import webview
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse

    logger.info("✓ FastAPI/Uvicorn/Webview imports successful")
except Exception as e:
    logger.critical(f"✗ Failed to import FastAPI stack: {e}", exc_info=True)
    sys.exit(1)

# ====================================================================
# UTILITY FUNCTIONS
# ====================================================================
def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource (works in dev and PyInstaller)"""
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
        logger.debug(f"Frozen mode, base: {base_path}")
    else:
        base_path = Path(__file__).parent.parent.parent
        logger.debug(f"Dev mode, base: {base_path}")

    full_path = base_path / relative_path
    logger.debug(f"Resource path '{relative_path}': {full_path} (exists: {full_path.exists()})")
    return full_path

# ====================================================================
# BACKEND API CREATION
# ====================================================================
def create_backend_api():
    """Create FastAPI backend with fallback endpoints"""
    api = FastAPI(title="Fortuna Backend")

    # Health endpoint (always works)
    @api.get("/health")
    async def health():
        return {"status": "ok", "service": "fortuna-monolith"}

    # Try to load full backend API
    try:
        logger.info("Attempting to load full backend API...")
        from web_service.backend import api as backend_api

        # Mount all routes from full backend
        logger.info(f"Full backend loaded, copying routes...")
        for route in backend_api.app.routes:
            api.routes.append(route)

        logger.info(f"✓ Full backend API loaded ({len(api.routes)} routes)")
        return api

    except ImportError as e:
        logger.warning(f"Full backend import failed: {e}")
        logger.warning("Using minimal API stub (no races/data endpoints)")

        # Stub endpoints
        @api.get("/races")
        async def get_races():
            return {
                "status": "error",
                "message": "Backend API not loaded",
                "sample": [
                    {"id": 1, "name": "Example Race", "status": "pending"}
                ]
            }

        @api.get("/")
        async def root():
            return {
                "status": "stub",
                "message": "Minimal backend mode (full API unavailable)",
                "error": str(e)
            }

        return api

    except Exception as e:
        logger.error(f"Unexpected error loading backend: {e}", exc_info=True)

        @api.get("/")
        async def root():
            return {"status": "error", "message": str(e)}

        return api

# ====================================================================
# FRONTEND SERVING
# ====================================================================
def create_app():
    """Create main FastAPI app with frontend + backend"""
    logger.info("Creating main FastAPI application...")
    app = FastAPI(title="Fortuna Monolith")

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("✓ CORS middleware configured")

    # Mount backend API
    logger.info("Mounting backend API at /api...")
    backend = create_backend_api()
    app.mount("/api", backend, name="backend")
    logger.info("✓ Backend mounted")

    # Frontend path
    frontend_path = get_resource_path("frontend_dist")
    index_file = frontend_path / "index.html"

    logger.info(f"Frontend path: {frontend_path}")
    logger.info(f"Index file: {index_file} (exists: {index_file.exists()})")

    if not frontend_path.exists():
        logger.error(f"Frontend directory not found: {frontend_path}")
        logger.warning("App will run but frontend will not be served")

        @app.get("/")
        async def root():
            return JSONResponse(
                {"error": "Frontend not bundled", "path": str(frontend_path)},
                status_code=500
            )

        return app

    # Mount static assets
    logger.info("Configuring frontend serving...")

    # Mount _next if it exists
    next_dir = frontend_path / "_next"
    if next_dir.exists():
        app.mount("/_next", StaticFiles(directory=str(next_dir)), name="next-static")
        logger.info(f"✓ Mounted /_next static files ({len(list(next_dir.iterdir()))} items)")
    else:
        logger.warning("_next directory not found (static assets won't load)")

    # Public assets
    public_dir = frontend_path / "public"
    if public_dir.exists():
        app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")
        logger.info("✓ Mounted /public")

    # Catch-all SPA routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Skip API routes
        if full_path.startswith("api/"):
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Exact file
        file_path = frontend_path / full_path
        if file_path.is_file():
            logger.debug(f"Serving file: {full_path}")
            return FileResponse(file_path)

        # Try with .html
        html_path = frontend_path / f"{full_path}.html"
        if html_path.is_file():
            return FileResponse(html_path)

        # SPA fallback to index.html
        if index_file.exists():
            logger.debug(f"SPA fallback for: {full_path}")
            return FileResponse(index_file)

        return JSONResponse(
            {"error": "Frontend not found", "path": str(frontend_path)},
            status_code=500
        )

    logger.info("✓ Frontend routing configured")
    return app

# ====================================================================
# BACKEND SERVER
# ====================================================================
def run_backend():
    """Run Uvicorn backend server"""
    try:
        logger.info("-" * 70)
        logger.info("STARTING BACKEND SERVER")
        logger.info("-" * 70)

        app = create_app()

        # Run server
        logger.info("Starting Uvicorn on http://127.0.0.1:8000")

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=False,
        )
    except Exception as e:
        logger.error(f"Backend crashed: {e}", exc_info=True)
        raise

# ====================================================================
# MAIN ENTRY POINT
# ====================================================================
def main():
    """Main application entry point"""
    try:
        logger.info("-" * 70)
        logger.info("STARTING FORTUNA MONOLITH")
        logger.info("-" * 70)

        # Start backend server in daemon thread
        logger.info("Starting backend thread...")
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        logger.info("✓ Backend thread started")

        # Wait for backend to initialize
        logger.info("Waiting 4 seconds for backend to start...")
        time.sleep(4)

        # Health check
        logger.info("Testing backend health...")
        backend_ready = False

        for attempt in range(1, 11):
            try:
                response = requests.get(
                    "http://127.0.0.1:8000/api/health",
                    timeout=2
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✓ Backend healthy: {data}")
                    backend_ready = True
                    break
                else:
                    logger.warning(f"Health check returned {response.status_code}")

            except requests.exceptions.ConnectionError:
                logger.debug(f"Backend not ready yet (attempt {attempt}/10)")
            except Exception as e:
                logger.warning(f"Health check error: {e}")

            time.sleep(1)

        if not backend_ready:
            logger.error("Backend failed health check - launching anyway but expect errors")

        # Launch webview
        logger.info("-" * 70)
        logger.info("LAUNCHING WEBVIEW")
        logger.info("-" * 70)

        webview.create_window(
            title="Fortuna Faucet",
            url="http://127.0.0.1:8000",
            width=1400,
            height=900,
            resizable=True,
            min_size=(800, 600),
            background_color="#1a1a1a",
        )

        logger.info("Starting webview event loop...")
        webview.start(debug=False)

        logger.info("Webview closed, exiting...")

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)

        # Try to show error dialog
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Fortuna Monolith Error",
                f"Failed to start:\n\n{str(e)}\n\nCheck %TEMP%\\fortuna-monolith.log"
            )
        except:
            pass

        sys.exit(1)

if __name__ == "__main__":
    main()
