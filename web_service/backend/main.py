import uvicorn
import sys
import os
from multiprocessing import freeze_support

# Force UTF-8 encoding for stdout and stderr, crucial for PyInstaller on Windows
os.environ["PYTHONUTF8"] = "1"

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
            os.path.join(project_root, "web_service"),
            os.path.join(project_root, "web_service", "backend"),
        ]

        # Insert paths at the beginning of sys.path in reverse order
        # to maintain the desired precedence.
        for path in reversed(paths_to_add):
            if path not in sys.path:
                sys.path.insert(0, path)
                print(f"INFO: Added path to sys.path: {path}")

    else:
        # Running as a normal script. The project root is two levels up.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"INFO: Added project root to sys.path: {project_root}")

def main():
    """
    Primary entry point for the Fortuna Faucet backend application.
    This function configures and runs the Uvicorn server.
    """
    # CRITICAL: This must be called before any other application imports.
    _configure_sys_path()

    # When packaged, we need to ensure multiprocessing and asyncio work correctly.
    if getattr(sys, "frozen", False):
        # CRITICAL for multiprocessing support in frozen mode on Windows.
        freeze_support()
        # CRITICAL for asyncio server behavior in frozen mode on Windows.
        import asyncio
        print("[BOOT] Applied WindowsSelectorEventLoopPolicy for PyInstaller")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


    from web_service.backend.config import get_settings
    from web_service.backend.port_check import check_port_and_exit_if_in_use
    # The 'app' object is needed for the server to run. Importing it here ensures
    # all its dependencies are resolved after the sys.path modification.
    from web_service.backend.api import app

    settings = get_settings()

    # In CI/CD, binding to 0.0.0.0 is more robust than 127.0.0.1.
    # We will override the host setting for the smoke test environment.
    run_host = settings.UVICORN_HOST
    if os.environ.get("FORTUNA_ENV") == "smoke-test":
        run_host = "0.0.0.0"
        print(f"INFO: Smoke test environment detected. Overriding host to '{run_host}'")


    # --- Port Sanity Check ---
    check_port_and_exit_if_in_use(settings.FORTUNA_PORT, run_host)

    print(f"INFO: Starting Uvicorn server...")
    print(f"      APP: web_service.backend.api:app")
    print(f"      HOST: {run_host}")
    print(f"      PORT: {settings.FORTUNA_PORT}")

    # For PyInstaller, it's more reliable to pass the app object directly
    # rather than a string, as string-based imports can be fragile.
    uvicorn.run(
        app,
        host=run_host,
        port=settings.FORTUNA_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
