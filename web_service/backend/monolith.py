# web_service/backend/monolith.py
import sys
import os
from pathlib import Path
import logging

# CRITICAL: Setup logging BEFORE anything else
def setup_logging():
    """Setup file logging for debugging"""
    if getattr(sys, 'frozen', False):
        # Running as EXE - log to temp directory
        log_dir = Path(os.environ.get('TEMP', '.'))
    else:
        log_dir = Path('.')

    log_file = log_dir / 'fortuna-monolith.log'

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging to: {log_file}")
    return logger

# Call this FIRST
logger = setup_logging()

logger.info("[MONOLITH] Starting up...")
logger.info(f"[MONOLITH] Frozen: {getattr(sys, 'frozen', False)}")
logger.info(f"[MONOLITH] Python: {sys.version}")
logger.info(f"[MONOLITH] CWD: {os.getcwd()}")

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

def create_app():
    """Create FastAPI app with proper routing for Next.js export"""
    from web_service.backend.api import app as backend_app

    app = FastAPI(title="Fortuna Monolith")

    # CRITICAL: Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount backend API FIRST (higher priority)
    app.mount("/api", backend_app, name="backend")

    # Get frontend path
    frontend_path = get_resource_path('frontend_dist')
    logger.info(f"[MONOLITH] Frontend path: {frontend_path}")
    logger.info(f"[MONOLITH] Frontend exists: {frontend_path.exists()}")

    if frontend_path.exists():
        if (frontend_path / "index.html").exists():
            logger.info("[MONOLITH] Found index.html")
        else:
            logger.warning("[MONOLITH] WARNING: index.html not found!")
            logger.warning(f"[MONOLITH] Contents: {list(frontend_path.iterdir())}")

        app.mount("/_next", StaticFiles(directory=str(frontend_path / "_next")), name="next-static")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            if full_path.startswith("api/"):
                return {"error": "API route should be handled by backend"}
            file_path = frontend_path / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            html_path = frontend_path / f"{full_path}.html"
            if html_path.is_file():
                return FileResponse(html_path)
            index_path = frontend_path / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            else:
                return {"error": "index.html not found", "path": str(index_path)}

        logger.info("[MONOLITH] Frontend routing configured")
    else:
        logger.error("[MONOLITH] ERROR: Frontend files not found!")

        @app.get("/")
        async def root():
            return {
                "error": "Frontend not found",
                "path": str(frontend_path),
                "expected_files": ["index.html", "_next/"],
            }

    return app

def run_backend():
    """Run backend with error handling"""
    try:
        logger.info("[MONOLITH] Creating FastAPI app...")
        app = create_app()

        logger.info("[MONOLITH] Starting Uvicorn on http://127.0.0.1:8000")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="debug"
        )
    except Exception as e:
        logger.error(f"[MONOLITH] ❌ Backend crashed: {e}", exc_info=True)
        sys.exit(1)

def main():
    """Main entry with comprehensive error handling"""
    try:
        logger.info("[MONOLITH] 🍀 Starting Fortuna Monolith...")

        logger.info("[MONOLITH] Starting backend thread...")
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()

        logger.info("[MONOLITH] ⏳ Waiting 5 seconds for backend...")
        time.sleep(5)

        logger.info("[MONOLITH] Testing backend health...")
        import requests
        for i in range(10):
            try:
                response = requests.get("http://127.0.0.1:8000/api/health", timeout=1)
                logger.info(f"[MONOLITH] Health check: {response.status_code}")
                if response.status_code == 200:
                    logger.info("[MONOLITH] ✅ Backend ready!")
                    break
            except Exception as e:
                logger.warning(f"[MONOLITH] Health check attempt {i+1}/10 failed: {e}")
                time.sleep(1)
        else:
            logger.error("[MONOLITH] ❌ Backend never became healthy!")

        logger.info("[MONOLITH] 🚀 Launching webview...")
        webview.create_window(
            title="Fortuna Faucet",
            url="http://127.0.0.1:8000",
            width=1400,
            height=900
        )

        webview.start(debug=True)
        logger.info("[MONOLITH] 👋 Application closed")

    except Exception as e:
        logger.error(f"[MONOLITH] ❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
