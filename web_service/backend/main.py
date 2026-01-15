import sys
from pathlib import Path
import uvicorn

# CRITICAL: Set up paths for PyInstaller
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    PROJECT_ROOT = Path(sys.executable).parent
else:
    # Running as script
    PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add project root to path
# Use insert(0) to ensure it's prioritized over other paths
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Now that the path is set, we can import our application modules
from web_service.backend.api import app
from web_service.backend.config import get_settings
from web_service.backend.port_check import check_port_and_exit_if_in_use


def main():
    """Main entry point for Fortuna Monolith."""
    settings = get_settings()

    # Ensure port is available before starting the server
    check_port_and_exit_if_in_use(settings.FORTUNA_PORT, settings.UVICORN_HOST)

    print(f"\n{'='*70}")
    print(f"🚀 FORTUNA FAUCET MONOLITH")
    print(f"{'='*70}")
    print(f"📍 Host: {settings.UVICORN_HOST}")
    print(f"📍 Port: {settings.FORTUNA_PORT}")
    print(f"🖥️  Mode: {'Frozen (Executable)' if getattr(sys, 'frozen', False) else 'Development'}")
    print(f"🌐 Frontend: http://{settings.UVICORN_HOST}:{settings.FORTUNA_PORT}/")
    print(f"⚙️  API Docs: http://{settings.UVICORN_HOST}:{settings.FORTUNA_PORT}/api/docs")
    print(f"{'='*70}\n")

    # Run the server using settings from the configuration
    uvicorn.run(
        app,
        host=settings.UVICORN_HOST,
        port=settings.FORTUNA_PORT,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    # Multiprocessing support for PyInstaller
    from multiprocessing import freeze_support
    freeze_support()
    main()
