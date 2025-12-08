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

# FIX: Ensure the current directory is in sys.path for relative imports in frozen state
sys.path.insert(0, str(Path(__file__).parent))

try:
    from main import app
except ImportError:
    # Fallback for different packaging structures
    from web_service.backend.main import app

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
