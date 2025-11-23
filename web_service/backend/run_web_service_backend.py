import sys
import os

# This script is the official entry point for the PyInstaller-built web service.
# Its sole purpose is to correctly configure the system path to ensure the
# 'web_service' package can be found, then execute the application.

def launch():
    """
    Configures sys.path and launches the main application.
    """
    # When the application is a frozen executable, the directory containing the
    # .exe is the effective root for our package.
    if getattr(sys, 'frozen', False):
        # The `_MEIPASS` attribute is a special path created by PyInstaller
        # that points to the temporary folder where bundled files are extracted.
        # However, for package resolution, we need the directory *containing*
        # the executable itself.
        project_root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # In a normal development environment, the project root is the
        # directory containing this script's parent's parent.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Add the project root to the Python path.
    # This allows the interpreter to find the 'web_service' package.
    sys.path.insert(0, project_root)

    # Now that the path is configured, we can safely import and run the main application.
    try:
        from web_service.backend.main import main
    except ModuleNotFoundError:
        print("Fatal Error: Could not find the 'web_service' package.", file=sys.stderr)
        print(f"Current sys.path: {sys.path}", file=sys.stderr)
        sys.exit(1)

    main()

if __name__ == "__main__":
    launch()
