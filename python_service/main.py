import uvicorn
import sys
import os
import asyncio
from multiprocessing import freeze_support

# Force UTF-8 encoding for stdout and stderr, crucial for PyInstaller on Windows
os.environ["PYTHONUTF8"] = "1"

# Import the 'app' object at the top level to make it accessible for import by other modules,
# such as diagnostic scripts in CI/CD.
from python_service.api import app, HTTPException

# This is the definitive entry point for the Fortuna Faucet backend service.
# It is designed to be compiled with PyInstaller.


def _configure_sys_path():
    """
    Dynamically adds project paths to sys.path.
    This is the robust solution to ensure that string-based imports like
    "web_service.backend.api:app" work correctly when the application is
    run from a PyInstaller executable. The `_MEIPASS` attribute is a temporary
    directory created by PyInstaller at runtime.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in a PyInstaller bundle. The project root is the _MEIPASS directory.
        project_root = os.path.abspath(sys._MEIPASS)

        # Aggressively add paths to resolve potential module lookup issues in frozen mode.
        paths_to_add = [
            project_root,
            os.path.join(project_root, "python_service"),
        ]

        # Insert paths at the beginning of sys.path in reverse order
        # to maintain the desired precedence.
        for path in reversed(paths_to_add):
            if path not in sys.path:
                sys.path.insert(0, path)
                print(f"INFO: Added path to sys.path: {path}")

    else:
        # Running as a normal script. The project root is one level up.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"INFO: Added project root to sys.path: {project_root}")


def main():
    _configure_sys_path()
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

    # CRITICAL FIX FOR PYINSTALLER on WINDOWS: Force event loop policy
    # This resolves a silent network binding failure where Uvicorn reports startup
    # but the OS never actually binds the port.
    if sys.platform == "win32" and getattr(sys, 'frozen', False):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("[BOOT] Applied WindowsSelectorEventLoopPolicy for PyInstaller", file=sys.stderr)

    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.FORTUNA_PORT, log_level="info")


if __name__ == "__main__":
    main()
