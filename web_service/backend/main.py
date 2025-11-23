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
    # When packaged, we need to adjust the Python path to ensure that the
    # top-level 'web_service' package can be found.
    if getattr(sys, "frozen", False):
        # CRITICAL for multiprocessing support in frozen mode on Windows.
        freeze_support()

        # Add the directory containing the executable to the path.
        # This is the most reliable way to ensure the package is found.
        project_root = os.path.dirname(os.path.abspath(sys.executable))
        sys.path.insert(0, project_root)

        # Also add the parent directory in case the executable is nested.
        parent_dir = os.path.abspath(os.path.join(project_root, os.pardir))
        sys.path.insert(0, parent_dir)

    # It's critical to import dependencies *after* the path has been manipulated.
    from web_service.backend.config import get_settings
    from web_service.backend.port_check import check_port_and_exit_if_in_use

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
