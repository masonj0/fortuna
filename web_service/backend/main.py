import sys
from pathlib import Path
import uvicorn
import logging
import traceback

# CRITICAL: Set up paths and logging for PyInstaller
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    PROJECT_ROOT = Path(sys.executable).parent
    LOG_FILE = PROJECT_ROOT / 'fortuna-monolith.log'
    # Redirect stdout and stderr to the log file to capture all output
    sys.stdout = open(LOG_FILE, 'w', encoding='utf-8')
    sys.stderr = sys.stdout
else:
    # Running as script
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    LOG_FILE = PROJECT_ROOT / 'fortuna-monolith-dev.log'

# Configure logging to write to the log file and original stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.__stdout__)
    ]
)
log = logging.getLogger(__name__)

# Add project root to path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
log.info(f"PROJECT_ROOT added to sys.path: {PROJECT_ROOT}")
log.info(f"Full sys.path: {sys.path}")

# Now that the path is set, we can import our application modules
from web_service.backend.api import app
from web_service.backend.config import get_settings
from web_service.backend.port_check import check_port_and_exit_if_in_use


def main():
    """Main entry point for Fortuna Monolith."""
    try:
        log.info("="*70)
        log.info("🚀 Fortuna Monolith Initializing...")
        log.info(f"Python Executable: {sys.executable}")
        log.info(f"Working Directory: {Path.cwd()}")
        log.info("="*70)

        settings = get_settings()

        log.info(f"Checking port {settings.FORTUNA_PORT} on host {settings.UVICORN_HOST}")
        check_port_and_exit_if_in_use(settings.FORTUNA_PORT, settings.UVICORN_HOST)
        log.info(f"Port {settings.FORTUNA_PORT} is available.")

        log.info(f"Host: {settings.UVICORN_HOST}")
        log.info(f"Port: {settings.FORTUNA_PORT}")
        log.info(f"Mode: {'Frozen (Executable)' if getattr(sys, 'frozen', False) else 'Development'}")
        log.info(f"Log file: {LOG_FILE}")

        log.info("Starting Uvicorn server...")
        uvicorn.run(
            app,
            host=settings.UVICORN_HOST,
            port=settings.FORTUNA_PORT,
            log_level="info",
            access_log=True,
        )
        log.info("Uvicorn server stopped gracefully.")

    except Exception as e:
        log.critical("--- !!! A FATAL ERROR OCCURRED DURING STARTUP !!! ---")
        log.critical(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    # Multiprocessing support for PyInstaller
    from multiprocessing import freeze_support
    freeze_support()
    main()
