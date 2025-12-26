import sys
import os
import asyncio
from multiprocessing import freeze_support
from pathlib import Path

# ============================================================================
# CRITICAL: Force PyInstaller to discover and bundle packages
# These imports are REQUIRED for PyInstaller's static analysis to work
# ============================================================================
import tenacity
import tenacity.asyncio
import uvicorn
import structlog
import fastapi
import starlette
import httpx
import redis
# ============================================================================


# Force UTF-8 encoding for stdout and stderr, crucial for PyInstaller on Windows
# PATCH #1: Added UTF-8 logging configuration
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# This is the definitive entry point for the Fortuna Faucet backend service.
# It is designed to be compiled with PyInstaller.

# [CRITICAL] Set Windows event loop policy for stable service operation
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# PATCH #1: get_asset_path() helper function
def get_asset_path(relative_path: str) -> Path:
    """
    Get the absolute path to an asset, which works for both development
    and PyInstaller bundled modes.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle.
        base_path = Path(sys._MEIPASS)
    else:
        # Running in a normal Python environment.
        # Assumes this script is in web_service/backend/
        base_path = Path(__file__).parent.parent.parent
    return base_path / relative_path

def main():
    """
    Primary entry point for the Fortuna Faucet backend application.
    This function configures and runs the Uvicorn server.
    """
    # [CRITICAL] This sys.path modification is essential for the application to find its
    # modules when running as a frozen executable from PyInstaller.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # The `sys._MEIPASS` attribute points to a temporary directory where PyInstaller unpacks the app.
        sys.path.insert(0, os.path.abspath(sys._MEIPASS))
        os.chdir(sys._MEIPASS)

    # Configure logging at the earliest point after path setup
    from web_service.backend.logging_config import configure_logging
    configure_logging()

    # Defer third-party imports until after sys.path is configured for PyInstaller
    import uvicorn
    import structlog

    log = structlog.get_logger(__name__)

    # When packaged, we need to ensure multiprocessing works correctly.
    if getattr(sys, "frozen", False):
        freeze_support()

    # Import the app object here after sys.path is configured.
    from web_service.backend.api import app, HTTPException
    from web_service.backend.config import get_settings
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from web_service.backend.port_check import check_port_and_exit_if_in_use

    settings = get_settings()

    run_host = settings.UVICORN_HOST
    if os.environ.get("FORTUNA_ENV") == "smoke-test":
        run_host = "0.0.0.0"
        log.info("Smoke test environment detected. Overriding host.", host=run_host)

    # --- Port Sanity Check ---
    check_port_and_exit_if_in_use(settings.FORTUNA_PORT, run_host)

    # --- Conditional UI Serving for Web Service Mode ---
    if os.environ.get("FORTUNA_MODE") == "webservice":
        log.info("Webservice mode enabled, attempting to serve UI.")
        # PATCH #1: Replaced hardcoded paths with the helper
        # The spec file bundles 'web_platform/frontend/out' into the 'ui' directory at the root.
        static_dir_relative = "ui" if getattr(sys, "frozen", False) else "web_platform/frontend/out"
        STATIC_DIR = get_asset_path(static_dir_relative)
        log.info("Static asset directory resolved.", path=str(STATIC_DIR))

        # PATCH #1: Adds startup verification to catch missing assets early
        if not STATIC_DIR.is_dir():
            log.error("CRITICAL: Static asset directory not found! UI will not be served.", path=str(STATIC_DIR))
        else:
            log.info("Mounting static assets.", directory=str(STATIC_DIR))
            # Mount the _next directory specifically for Next.js assets
            next_dir = STATIC_DIR / "_next"
            if next_dir.is_dir():
                app.mount("/_next", StaticFiles(directory=str(next_dir)), name="next-static")
                log.info("Mounted '/_next' static path.")
            else:
                log.warning("'_next' directory not found in static assets. Frontend may not render correctly.", path=str(next_dir))

            # Serve the main index.html for any non-API path.
            @app.get("/{full_path:path}", include_in_schema=False)
            async def serve_frontend(full_path: str):
                api_prefixes = ("api/", "docs", "openapi.json", "redoc")
                if any(full_path.startswith(p) for p in api_prefixes) or full_path == "health":
                    # Let FastAPI handle API routes. A 404 will be raised naturally if no route matches.
                    return

                index_path = STATIC_DIR / "index.html"
                if index_path.exists():
                    return FileResponse(str(index_path))
                else:
                    log.error("index.html not found in static directory.", path=str(index_path))
                    raise HTTPException(
                        status_code=404,
                        detail="Frontend not found. Please build the frontend and ensure it's in the correct location.",
                    )
            log.info("Configured catch-all route to serve 'index.html'.")

    log.info("Starting Uvicorn server...",
             app="web_service.backend.api:app",
             host=run_host,
             port=settings.FORTUNA_PORT)

    uvicorn.run(
        "web_service.backend.api:app", # Use string import to be reload-friendly
        host=run_host,
        port=settings.FORTUNA_PORT,
        log_level="info",
        reload=False # Reload should be disabled for production/service
    )

if __name__ == "__main__":
    main()
