import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import uvicorn
import multiprocessing
import threading
from pathlib import Path
import asyncio
import logging

# PATCH #2: This entire file is replaced to ensure correct service behavior.

# --- UTF-8 Logging Configuration ---
# Must be configured BEFORE any logging calls.
def configure_utf8_logging():
    """Configures stdout/stderr to use UTF-8 encoding."""
    if sys.stdout and sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr and sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
    # Basic logging config
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Path Bootstrapping ---
def _bootstrap_path():
    """
    Ensures the application's root directories are on the Python path.
    This is critical for PyInstaller's frozen executables to find modules.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle.
        sys.path.insert(0, sys._MEIPASS)
    else:
        # Running from source.
        project_root = str(Path(__file__).parent.parent.parent)
        sys.path.insert(0, project_root)

# CRITICAL: Apply path and logging fixes at the earliest possible moment.
_bootstrap_path()
configure_utf8_logging()
log = logging.getLogger(__name__)

# --- Resilient App Import ---
try:
    log.info("Attempting to import 'app' from api...")
    from web_service.backend.api import app
    log.info("Successfully imported 'app'.")
except (ImportError, ModuleNotFoundError) as e:
    log.error(f"FATAL: All import attempts failed: {e}. Cannot start service.")
    sys.exit(1)

class FortunaSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = 'FortunaWebService'
    _svc_display_name_ = 'Fortuna Faucet Backend Service'
    _svc_description_ = 'Data aggregation and analysis engine.'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.server = None
        self.server_thread = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        if self.server:
            # Uvicorn's server has a 'should_exit' flag that can be set
            # to signal a graceful shutdown.
            self.server.should_exit = True
            log.info("Server shutdown signaled.")

    def SvcDoRun(self):
        # CRITICAL: Change CWD to the executable's directory.
        # The default for a Windows Service is C:\Windows\System32,
        # which will break all relative path logic.
        if getattr(sys, 'frozen', False):
            exe_path = os.path.dirname(sys.executable)
            os.chdir(exe_path)
            log.info(f"Service running in frozen mode. CWD set to: {exe_path}")

        # CRITICAL: Set the asyncio event loop policy for Windows.
        # The default ProactorEventLoop is not compatible with services.
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            log.info("WindowsSelectorEventLoopPolicy applied for asyncio.")

        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )

        log.info(f"Starting {self._svc_display_name_}...")

        try:
            # Configure Uvicorn to run the FastAPI app.
            # Host '0.0.0.0' is often more reliable in containerized/CI environments.
            config = uvicorn.Config(
                app,
                host='0.0.0.0',
                port=8102,
                log_config=None, # We are using our own logger
                reload=False
            )
            self.server = uvicorn.Server(config)

            # Run the server in a separate thread so we can listen for stop events.
            self.server_thread = threading.Thread(target=self.server.run)
            self.server_thread.start()
            log.info("Uvicorn server thread started.")

            # Wait for the stop signal.
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            log.info("Stop signal received. Initiating shutdown...")

        except Exception as e:
            # Log any exceptions that occur during service startup or execution.
            log.error(f"A critical error occurred in SvcDoRun: {e}", exc_info=True)
            self.SvcStop() # Attempt a graceful stop on error.
        finally:
            # Ensure the server thread is joined upon exit.
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join()
            log.info(f"{self._svc_display_name_} has stopped.")


def main():
    """Main entry point for command-line interaction."""
    # This support is critical for PyInstaller.
    multiprocessing.freeze_support()

    if len(sys.argv) == 1:
        # Standard service startup logic
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FortunaSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Command-line arguments like 'install', 'start', 'stop', 'remove'.
        win32serviceutil.HandleCommandLine(FortunaSvc)

if __name__ == '__main__':
    main()
