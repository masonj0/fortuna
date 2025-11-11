import uvicorn
import sys
import os
from multiprocessing import freeze_support

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
    if getattr(sys, 'frozen', False):
        # CRITICAL: This is required for multiprocessing to work correctly when
        # the application is frozen with PyInstaller on Windows.
        freeze_support()

        # If the application is run as a bundle, the PyInstaller bootloader
        # extends the sys module by a flag frozen=True and sets the app
        # path into variable _MEIPASS'.
        application_path = os.path.dirname(sys.executable)
        sys.path.append(application_path)
        # Also add the parent directory to allow for relative imports.
        sys.path.append(os.path.join(application_path, '..'))

    # It's critical to import the app object *after* the path has been manipulated.
    from python_service.api import app
    from python_service.config import get__settings

    settings = get_settings()

    uvicorn.run(
        app,
        host=settings.UVICORN_HOST,
        port=settings.UVICORN_PORT,
        log_level="info"
    )

if __name__ == "__main__":
    main()
