import uvicorn
import sys
import os
from multiprocessing import freeze_support

# Force UTF-8 encoding for stdout and stderr, crucial for PyInstaller on Windows
os.environ["PYTHONUTF8"] = "1"

# This is the definitive entry point for the Fortuna Faucet backend service.
# It is designed to be compiled with PyInstaller.


def main():
    """
    Primary entry point for the Fortuna Faucet backend application.
    This function configures and runs the Uvicorn server.
    It's crucial to launch the app this way to ensure PyInstaller's bootloader
    can correctly resolve the package context.
    """
    # When packaged, we need to ensure multiprocessing works correctly.
    if getattr(sys, "frozen", False):
        # CRITICAL for multiprocessing support in frozen mode on Windows.
        freeze_support()

    from python_service.api import app, HTTPException
    from python_service.config import get_settings
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from python_service.port_check import check_port_and_exit_if_in_use

    settings = get_settings()

    # --- Port Sanity Check ---
    # Before doing anything else, ensure the target port is not already in use.
    # This prevents a common and confusing crash scenario on startup.
    check_port_and_exit_if_in_use(settings.FORTUNA_PORT, settings.UVICORN_HOST)

    # --- Conditional UI Serving for Web Service Mode ---
    # Only serve the UI if the FORTUNA_MODE environment variable is set to 'webservice'.
    # This prevents the Electron-packaged backend from trying to serve files it doesn't have.
    if os.environ.get("FORTUNA_MODE") == "webservice":
        # Define the path to the static UI files, accommodating PyInstaller's bundle.
        if getattr(sys, "frozen", False):
            # In a bundled app, the UI files are in the '_MEIPASS/ui' directory.
            STATIC_DIR = os.path.join(sys._MEIPASS, "ui")
        else:
            # In development, they are in the frontend's output directory.
            STATIC_DIR = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "web_platform", "frontend", "out")
            )

        # Mount the static assets directory for CSS, JS, etc.
        if os.path.exists(os.path.join(STATIC_DIR, "_next")):
            app.mount("/_next", StaticFiles(directory=os.path.join(STATIC_DIR, "_next")), name="next")

        # Serve the main index.html for any non-API path.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str):
            if full_path.startswith("api/") or full_path.startswith("docs") or full_path == "health":
                # This is an API route, let FastAPI handle it.
                # A 404 will be raised naturally if no route matches.
                return

            index_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            else:
                # This will only be hit if the frontend files are missing entirely.
                raise HTTPException(
                    status_code=404,
                    detail="Frontend not found. Please build the frontend and ensure it's in the correct location.",
                )

    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.FORTUNA_PORT, log_level="info")


if __name__ == "__main__":
    main()
