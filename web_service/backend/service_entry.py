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

# --- Resilient Import Block ---
# This block is designed to robustly locate the `main` module and its `app` object,
# whether running from source, as a PyInstaller bundle, or as a Windows Service.

def _bootstrap_path():
    """
    Ensures the application's root directories are on the Python path.
    This is critical for PyInstaller's frozen executables to find modules.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # We are running in a PyInstaller bundle.
        # The `_MEIPASS` directory is the root of our bundled files.
        # In our `--onedir` build, this is where `main.py`'s content is.
        sys.path.insert(0, sys._MEIPASS)
    else:
        # We are running from source.
        # The entry point is in `web_service/backend`, so we need to add the project root.
        project_root = str(Path(__file__).parent.parent.parent)
        sys.path.insert(0, project_root)

_bootstrap_path()

try:
    # This is the most direct import path and should work when the CWD
    # is correctly set to the directory containing the executable.
    print(f"[service_entry] Attempting direct import of 'main:app'...")
    from main import app
    print(f"[service_entry] Direct import successful.")
except (ImportError, ModuleNotFoundError) as e:
    print(f"[service_entry] Direct import failed: {e}. Attempting namespace import...")
    try:
        # This is a fallback for environments where the `web_service` namespace is preserved.
        from web_service.backend.main import app
        print(f"[service_entry] Namespace import successful.")
    except (ImportError, ModuleNotFoundError) as e2:
        print(f"[service_entry] All import attempts failed: {e2}. Cannot start service.")
        sys.exit(1) # Exit if the app cannot be imported, to prevent service start failure.

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
            self.server.should_exit = True

    def SvcDoRun(self):
        # When running as a Windows Service, the default working directory is System32,
        # which can cause issues with relative paths. This fix changes the working
        # directory to the location of the executable.
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))

        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))

        config = uvicorn.Config(app, host='127.0.0.1', port=8102, log_config=None, reload=False)
        self.server = uvicorn.Server(config)

        # Run the server in a separate thread
        self.server_thread = threading.Thread(target=self.server.run)
        self.server_thread.start()

        # Wait for the stop event
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

        # Wait for the server thread to finish
        self.server_thread.join()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FortunaSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FortunaSvc)
