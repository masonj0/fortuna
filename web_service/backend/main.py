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
    # When packaged, the executable's path needs to be added to sys.path
    # to ensure that modules can be found.
    if getattr(sys, "frozen", False):
        # CRITICAL: This is required for multiprocessing to work correctly when
        # the application is frozen with PyInstaller on Windows.
        freeze_support()

        # If the application is run as a bundle, the PyInstaller bootloader
        # extends the sys module by a flag frozen=True and sets the app
        # path into variable _MEIPASS'.
        application_path = os.path.dirname(sys.executable)
        sys.path.append(application_path)
        # Also add the parent directory to allow for relative imports.
        sys.path.append(os.path.join(application_path, ".."))

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
