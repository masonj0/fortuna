# run_web_service.py
# This is the single, authoritative entry point for the PyInstaller-built web service.
import sys
import os
import uvicorn
import multiprocessing

def main():
    """
    Configures sys.path and launches the Uvicorn server for the web service.
    This script is designed to be the single entry point for the PyInstaller executable.
    """
    # Required for PyInstaller on Windows when using multiprocessing, which Uvicorn might.
    multiprocessing.freeze_support()

    # When running as a PyInstaller bundle, sys.executable is the path to the .exe.
    # The 'web_service' package is bundled relative to this location. We need to ensure
    # the root is on the path so that 'import web_service' works.
    if getattr(sys, 'frozen', False):
        # In a frozen app, the root is the directory containing the executable.
        project_root = os.path.dirname(sys.executable)
        sys.path.insert(0, project_root)
        # The _MEIPASS directory is where bundled files are, ensure it's on the path too.
        if hasattr(sys, '_MEIPASS'):
             sys.path.insert(0, sys._MEIPASS)
    else:
        # In a development environment, the project root is the current directory.
        project_root = os.path.abspath(os.path.dirname(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

    # Directly import the app object. This ensures the import happens while the
    # sys.path is correctly configured, avoiding the deferred string import
    # issue with PyInstaller.
    from web_service.backend.api import app

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("FORTUNA_PORT", 8088)),
        reload=False
    )

if __name__ == "__main__":
    main()
