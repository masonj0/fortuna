#!/usr/bin/env python
"""Fortuna Monolith - Unified Frontend + Backend Application"""

import asyncio
import os
import sys
from multiprocessing import freeze_support

# UTF-8 encoding for Windows PyInstaller
os.environ["PYTHONUTF8"] = "1"

from web_service.backend.api import app


def _configure_sys_path():
    """Configure Python path for both dev and frozen environments."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller frozen environment
        project_root = os.path.abspath(sys._MEIPASS)
        paths = [project_root, os.path.join(project_root, "web_service")]
        for path in reversed(paths):
            if path not in sys.path:
                sys.path.insert(0, path)
    else:
        # Development environment
        project_root = os.path.abspath(os.path.dirname(__file__) + "/../..")
        if project_root not in sys.path:
            sys.path.insert(0, project_root)


def main():
    """Main entry point for Fortuna Monolith."""
    _configure_sys_path()

    if getattr(sys, "frozen", False):
        freeze_support()
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from web_service.backend.config import get_settings
    from web_service.backend.port_check import check_port_and_exit_if_in_use

    import uvicorn

    settings = get_settings()

    # Ensure port is available
    check_port_and_exit_if_in_use(settings.FORTUNA_PORT, settings.UVICORN_HOST)

    print(f"\n{'='*70}")
    print(f"🚀 FORTUNA FAUCET MONOLITH 3.0")
    print(f"{'='*70}")
    print(f"📍 Host: {settings.UVICORN_HOST}")
    print(f"📍 Port: {settings.FORTUNA_PORT}")
    print(f"🖥️  Mode: {'Frozen (Windows Executable)' if getattr(sys, 'frozen', False) else 'Development'}")
    print(f"🌐 Frontend: http://{settings.UVICORN_HOST}:{settings.FORTUNA_PORT}/")
    print(f"⚙️  API: http://{settings.UVICORN_HOST}:{settings.FORTUNA_PORT}/api/")
    print(f"📚 Docs: http://{settings.UVICORN_HOST}:{settings.FORTUNA_PORT}/docs")
    print(f"{'='*70}\\n")

    # Run the server
    uvicorn.run(
        app,
        host=settings.UVICORN_HOST,
        port=settings.FORTUNA_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
