import uvicorn
import sys
import os
import asyncio
from multiprocessing import freeze_support

# Force UTF-8 encoding for stdout and stderr, crucial for PyInstaller on Windows
os.environ["PYTHONUTF8"] = "1"

# Import the 'app' object at the top level
from web_service.backend.api import app, HTTPException


def _configure_sys_path():
    """
    Dynamically adds project paths to sys.path.
    This is essential for PyInstaller to correctly resolve imports.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in a PyInstaller bundle
        project_root = os.path.abspath(sys._MEIPASS)
        paths_to_add = [
            project_root,
            os.path.join(project_root, "web_service/backend"),
        ]
        for path in reversed(paths_to_add):
            if path not in sys.path:
                sys.path.insert(0, path)
                print(f"INFO: Added path to sys.path: {path}")
    else:
        # Running as a normal script
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"INFO: Added project root to sys.path: {project_root}")


def main():
    """
    Primary entry point for the Fortuna Faucet backend application.
    """
    # Configure paths before any other imports
    _configure_sys_path()

    # Multiprocessing support for frozen (PyInstaller) mode on Windows
    if getattr(sys, "frozen", False):
        freeze_support()

        # Set event loop policy for Windows
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            print("[BOOT] ✓ Applied WindowsSelectorEventLoopPolicy for PyInstaller", file=sys.stderr)

    from web_service.backend.config import get_settings
    from web_service.backend.port_check import check_port_and_exit_if_in_use

    settings = get_settings()

    # Sanity check: ensure the target port is not already in use
    check_port_and_exit_if_in_use(settings.FORTUNA_PORT, settings.UVICORN_HOST)

    print(f"\\n{'='*60}")
    print(f"🚀 Starting Fortuna Faucet Backend")
    print(f" {'='*60}")
    print(f"Host: {settings.UVICORN_HOST}")
    print(f"Port: {settings.FORTUNA_PORT}")
    print(f"Mode: {'Production (Frozen)' if getattr(sys, 'frozen', False) else 'Development'}")
    print(f"Frontend will be served from: http://{settings.UVICORN_HOST}:{settings.FORTUNA_PORT}/")
    print(f"API endpoints available at: http://{settings.UVICORN_HOST}:{settings.FORTUNA_PORT}/api/")
    print(f" {'='*60}\\n")

    # Run the Uvicorn server
    uvicorn.run(
        app,
        host=settings.UVICORN_HOST,
        port=settings.FORTUNA_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
