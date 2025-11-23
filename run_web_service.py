# run_web_service.py
# This is the official, root-level entry point for the PyInstaller-built web service.

import sys
import os

def launch():
    """
    Configures sys.path to include the application's root directory
    and launches the main web service application.
    """
    # When running as a PyInstaller bundle, the sys.executable is the path to the .exe.
    # The 'web_service' package is in the same directory, so we need to add this
    # directory to the path.
    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
        sys.path.insert(0, project_root)
    else:
        # In a development environment, the project root is the current directory.
        project_root = os.path.abspath(os.path.dirname(__file__))
        sys.path.insert(0, project_root)

    # Now that the path is correctly configured, we can import and run the app.
    from web_service.backend.run_web_service_backend import launch as launch_app
    launch_app()

if __name__ == "__main__":
    launch()
