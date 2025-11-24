# run_web_service.py
# This is the single, authoritative entry point for the PyInstaller-built web service.
import sys
import os
import uvicorn
import multiprocessing
import asyncio
import traceback

def main():
    """
    Configures sys.path and launches the Uvicorn server for the web service.
    This script is designed to be the single entry point for the PyInstaller executable.
    """
    # Required for PyInstaller on Windows when using multiprocessing.
    multiprocessing.freeze_support()

    # Path configuration for both frozen and development environments.
    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
        sys.path.insert(0, project_root)
        if hasattr(sys, '_MEIPASS'):
             sys.path.insert(0, sys._MEIPASS)
    else:
        project_root = os.path.abspath(os.path.dirname(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

    # CRITICAL FIX FOR PYINSTALLER on WINDOWS: Force event loop policy
    if sys.platform == "win32" and getattr(sys, 'frozen', False):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("[BOOT] Applied WindowsSelectorEventLoopPolicy for PyInstaller", file=sys.stderr)

    # Explicit server config and run with robust error handling
    try:
        print("[BOOT] Configuring Uvicorn server...", file=sys.stderr)
        # Use the port from the CI environment, defaulting to 8102
        port = int(os.getenv("FORTUNA_PORT", 8102))

        config = uvicorn.Config(
            "web_service.backend.api:app",
            host="0.0.0.0",
            port=port,
            log_level="info",
            workers=1
        )

        server = uvicorn.Server(config)

        print(f"[BOOT] Starting server on port {port}...", file=sys.stderr)
        server.run()
        print("[BOOT] Server stopped.", file=sys.stderr)

    except Exception as e:
        # If any exception occurs during startup, log it to a file for forensics.
        # This is critical for diagnosing silent crashes in the CI environment.
        error_log_path = "fatal_boot_error.log"
        print(f"[FATAL BOOT ERROR] Server failed to start: {e}", file=sys.stderr)
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write("A fatal error occurred during Uvicorn server startup:\n")
            f.write(f"Exception Type: {type(e).__name__}\n")
            f.write(f"Exception Args: {e.args}\n\n")
            traceback.print_exc(file=f)
        print(f"[FATAL BOOT ERROR] Full traceback written to {error_log_path}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
