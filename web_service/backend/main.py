import uvicorn
import sys
import os
from multiprocessing import freeze_support

from web_service.backend.config import get_settings
from web_service.backend.port_check import check_port_and_exit_if_in_use


# Force UTF-8 encoding for stdout and stderr, crucial for PyInstaller on Windows
os.environ["PYTHONUTF8"] = "1"

# This is the definitive entry point for the Fortuna Faucet backend service.
# It is designed to be compiled with PyInstaller.

def _configure_sys_path():
    """
    Dynamically adds the project root to sys.path.
    This is the robust solution to ensure that string-based imports like
    "web_service.backend.api:app" work correctly when the application is
    run from a PyInstaller executable. The `_MEIPASS` attribute is a temporary
    directory created by PyInstaller at runtime.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in a PyInstaller bundle.
        # The project root IS the _MEIPASS directory itself.
        project_root = os.path.abspath(sys._MEIPASS)
    else:
        # Running as a normal script.
        # The project root is two levels above this file's directory.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        print(f"INFO: Added project root to sys.path: {project_root}")

def main():
    """
    Primary entry point for the Fortuna Faucet backend application.
    This function configures and runs the Uvicorn server.
    It is launched by an entry-point script that handles path configuration.
    """
    # When packaged, we need to ensure multiprocessing works correctly.
    if getattr(sys, "frozen", False):
        # CRITICAL for multiprocessing support in frozen mode on Windows.
        freeze_support()

    # CRITICAL: This must be called before any other application imports.
    _configure_sys_path()

    settings = get_settings()

    # --- Port Sanity Check ---
    check_port_and_exit_if_in_use(settings.FORTUNA_PORT, settings.UVICORN_HOST)

    # Use string-based app import for PyInstaller compatibility
    uvicorn.run(
        "web_service.backend.api:app",
        host=settings.UVICORN_HOST,
        port=settings.FORTUNA_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
