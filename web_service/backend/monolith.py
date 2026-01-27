"""
Fortuna Monolith - Single executable frontend + backend
Production-grade with enhanced error handling, user-friendly startup, and better logging

IMPORTANT: Uses WinForms instead of CEF for Python 3.10 compatibility
(CEFPython3 v66.0 doesn't support Python 3.10.11)
"""
import sys
import os
from pathlib import Path
import logging
import io
import threading
import time
import json
from contextlib import suppress

# ====================================================================
# CONSTANTS & CONFIGURATION
# ====================================================================
APP_NAME = "Fortuna Faucet"
APP_VERSION = "1.0.0"
API_HOST = "127.0.0.1"
API_PORT = 8000
BACKEND_STARTUP_TIMEOUT = 10
HEALTH_CHECK_ATTEMPTS = 10
HEALTH_CHECK_INTERVAL = 1

# ====================================================================
# LOGGING SETUP (BEFORE ANYTHING ELSE)
# ====================================================================
def _get_log_file() -> Path:
    """Get log file path (works in both dev and frozen modes)"""
    if getattr(sys, "frozen", False):
        log_dir = Path(os.environ.get("TEMP", "."))
    else:
        log_dir = Path(".")
    return log_dir / "fortuna-monolith.log"

def _force_utf8_stream(stream):
    """Ensure stream uses UTF-8 encoding"""
    if hasattr(stream, "reconfigure"):
        with suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")
            return stream

    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream

    with suppress(Exception):
        return io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")

    return stream

def setup_logging():
    """Configure logging to both file and console"""
    log_file = _get_log_file()

    # Force UTF-8 on stdout/stderr
    sys.stdout = _force_utf8_stream(sys.stdout)
    sys.stderr = _force_utf8_stream(sys.stderr)

    # Logging handlers
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)

    # Format with timestamps
    formatter = logging.Formatter(
        "[%(levelname)-8s] %(asctime)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Setup root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler],
    )

    logger = logging.getLogger("fortuna")
    return logger

logger = setup_logging()

# Banner
logger.info("=" * 70)
logger.info(f"{APP_NAME} v{APP_VERSION} - Starting up")
logger.info("=" * 70)
logger.info(f"Mode: {'Frozen EXE' if getattr(sys, 'frozen', False) else 'Development'}")
logger.info(f"Python: {sys.version.split()[0]}")

# ====================================================================
# UI HELPERS (DEFINE BEFORE IMPORTS)
# ====================================================================
def show_error_dialog(title: str, message: str):
    """Show error dialog (fallback if no GUI available)"""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
    except:
        # If tkinter fails, just log it
        logger.error(f"{title}: {message}")

# ====================================================================
# FORCE PYINSTALLER TO INCLUDE DEPENDENCIES (TOP-LEVEL IMPORTS)
# ====================================================================
if False:  # Never executes, but PyInstaller sees the imports
    import fastapi
    import uvicorn
    import webview
    import pydantic
    import starlette
    import requests
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse

# ====================================================================
# IMPORT DEPENDENCIES WITH FRIENDLY ERROR HANDLING
# ====================================================================
def _import_dependencies():
    """Import all required modules with descriptive error messages"""
    try:
        global uvicorn, webview, FastAPI, StaticFiles, CORSMiddleware, FileResponse, JSONResponse, requests

        import requests
        import uvicorn
        import webview
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import FileResponse, JSONResponse

        logger.info("OK - All dependencies loaded successfully")
        return True
    except ImportError as e:
        logger.critical(f"FAILED - Missing dependency: {e}")
        show_error_dialog(
            "Missing Dependencies",
            f"Could not load required library:\n{str(e)}\n\n"
            "Ensure all packages in requirements.txt are installed:\n"
            "pip install -r web_service/backend/requirements.txt"
        )
        return False
    except Exception as e:
        logger.critical(f"FAILED - Unexpected import error: {e}", exc_info=True)
        show_error_dialog(
            "Startup Error",
            f"Unexpected error during startup:\n{str(e)}\n\n"
            f"Check the log file for details:\n{_get_log_file()}"
        )
        return False

if not _import_dependencies():
    sys.exit(1)

# ====================================================================
# UTILITY FUNCTIONS
# ====================================================================
def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to bundled resources"""
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent

    full_path = base_path / relative_path
    return full_path

# ====================================================================
# API CREATION
# ====================================================================
def create_backend_api():
    """Create FastAPI instance with fallback support"""
    # Use the lifespan from the main API to ensure engine initialization
    try:
        from web_service.backend.api import lifespan as backend_lifespan
        api = FastAPI(title="Fortuna Backend", lifespan=backend_lifespan)
    except ImportError:
        api = FastAPI(title="Fortuna Backend")

    @api.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "service": "fortuna-monolith",
            "version": APP_VERSION
        }

    try:
        logger.info("Attempting to load full backend API...")
        from web_service.backend.api import router as backend_router

        # Include the router directly instead of copying routes from app.
        # This avoids double-prefixing (/api/api/...) and accidental copying
        # of static mounts and middleware from the standalone app instance.
        api.include_router(backend_router)

        logger.info("OK - Full backend API router included")
        return api

    except (ImportError, AttributeError) as e:
        logger.warning(f"Full backend import failed: {e}")
        logger.info("Running in minimal mode (basic endpoints only)")

        # Provide stub endpoints
        @api.get("/races")
        async def get_races():
            return {
                "status": "error",
                "message": "Full API not available",
                "sample": [{"id": 1, "name": "Example Race", "status": "pending"}]
            }

        return api

    except Exception as e:
        logger.error(f"Unexpected error loading backend: {e}", exc_info=True)
        return api

# ====================================================================
# APP CREATION
# ====================================================================
def create_app():
    """Create main FastAPI application"""
    logger.info("Creating FastAPI application...")
    app = FastAPI(title="Fortuna Monolith")

    # CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("OK - CORS middleware configured")

    # Mount backend API
    logger.info("Mounting backend API at /api...")
    backend = create_backend_api()
    app.mount("/api", backend, name="backend")

    # Setup frontend serving
    frontend_path = get_resource_path("frontend_dist")
    index_file = frontend_path / "index.html"

    logger.info(f"Frontend path: {frontend_path}")

    if not frontend_path.exists():
        logger.error("Frontend directory not found - app will run without UI")

        @app.get("/")
        async def fallback():
            return JSONResponse(
                {"message": "Frontend not available", "api": "/api/health"},
                status_code=503
            )
        return app

    # Mount static files
    logger.info("Configuring static file serving...")

    # Mount Next.js build output
    next_dir = frontend_path / "_next"
    if next_dir.exists():
        app.mount("/_next", StaticFiles(directory=str(next_dir)), name="next")
        logger.info("OK - Static assets mounted")

    public_dir = frontend_path / "public"
    if public_dir.exists():
        app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")

    # SPA routing - catch all unmapped routes and serve index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Skip API routes
        if full_path.startswith("api/"):
            return JSONResponse({"error": "Not found"}, status_code=404)

        # Try exact file
        file_path = frontend_path / full_path
        try:
            if file_path.is_file() and file_path.is_relative_to(frontend_path):
                return FileResponse(file_path)
        except (ValueError, RuntimeError):
            pass

        # Try with .html extension
        html_path = frontend_path / f"{full_path}.html"
        try:
            if html_path.is_file() and html_path.is_relative_to(frontend_path):
                return FileResponse(html_path)
        except (ValueError, RuntimeError):
            pass

        # SPA fallback to index
        if index_file.exists():
            return FileResponse(index_file)

        return JSONResponse({"error": "Not found"}, status_code=404)

    logger.info("OK - SPA routing configured")
    return app

# ====================================================================
# BACKEND SERVER
# ====================================================================
def run_backend():
    """Run Uvicorn server"""
    try:
        logger.info("-" * 70)
        logger.info("STARTING BACKEND SERVER")
        logger.info(f"API: http://{API_HOST}:{API_PORT}")
        logger.info("-" * 70)

        app = create_app()

        # Run Uvicorn
        uvicorn.run(
            app,
            host=API_HOST,
            port=API_PORT,
            log_level="warning",
            access_log=False,
        )
    except OSError as e:
        logger.critical(f"Port {API_PORT} is already in use: {e}")
        raise
    except Exception as e:
        logger.critical(f"Backend error: {e}", exc_info=True)
        raise

# ====================================================================
# HEALTH CHECKS
# ====================================================================
def check_backend_health(max_attempts: int = HEALTH_CHECK_ATTEMPTS) -> bool:
    """Check if backend is responding"""
    logger.info("Testing backend health...")

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                f"http://{API_HOST}:{API_PORT}/api/health",
                timeout=2
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"OK - Backend responding: {data}")
                return True

        except requests.ConnectionError:
            if attempt < max_attempts:
                logger.debug(f"Attempt {attempt}/{max_attempts} - waiting...")
                time.sleep(HEALTH_CHECK_INTERVAL)
        except Exception as e:
            logger.warning(f"Health check error: {e}")

    logger.warning(f"Backend did not respond after {max_attempts} attempts")
    return False

# ====================================================================
# MAIN APPLICATION
# ====================================================================
def main():
    """Main entry point"""
    try:
        logger.info("-" * 70)
        logger.info(f"STARTING {APP_NAME}")
        logger.info("-" * 70)

        # Start backend in background
        logger.info("Starting backend server...")
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        logger.info("OK - Backend thread started")

        # Wait for backend to initialize
        logger.info(f"Waiting for backend to be ready (max {BACKEND_STARTUP_TIMEOUT}s)...")
        time.sleep(2)

        # Health check
        backend_ready = check_backend_health()

        if not backend_ready:
            logger.warning("Backend not responding - launching UI anyway")

        # Launch UI
        logger.info("-" * 70)
        logger.info("LAUNCHING USER INTERFACE")
        logger.info("-" * 70)

        try:
            # Use WinForms GUI (default on Windows, compatible with Python 3.10)
            # CEF is not used here to avoid Python version compatibility issues
            webview.create_window(
                title=APP_NAME,
                url=f"http://{API_HOST}:{API_PORT}",
                width=1400,
                height=900,
                resizable=True,
                min_size=(800, 600),
                background_color="#1a1a1a",
            )

            logger.info("Starting webview event loop...")
            # Don't specify gui='cef' - let pywebview auto-detect WinForms
            webview.start(debug=False)

        except Exception as e:
            logger.error(f"Webview error: {e}", exc_info=True)
            # Fall back to browser message
            logger.info(f"Open http://{API_HOST}:{API_PORT} in your browser")
            input("Press ENTER to exit...")

        logger.info(f"{APP_NAME} closed normally")

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        show_error_dialog(
            f"{APP_NAME} Error",
            f"Application failed to start:\n{str(e)}\n\n"
            f"Please check the log file at:\n{_get_log_file()}"
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
