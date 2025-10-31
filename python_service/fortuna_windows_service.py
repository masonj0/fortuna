# fortuna_windows_service.py

import logging
import os
import sys

import servicemanager
import win32event
import win32service
import win32serviceutil

# Add the service's directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fortuna_service import FortunaBackgroundService


class FortunaWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "FortunaV8Service"
    _svc_display_name_ = "Fortuna V8 Racing Analysis Service"
    _svc_description_ = "Continuously fetches and analyzes horse racing data."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.fortuna_service = FortunaBackgroundService()
        # Configure logging to use the Windows Event Log
        logging.basicConfig(
            level=logging.INFO,
            format="%(name)s - %(levelname)s - %(message)s",
            handlers=[servicemanager.LogHandler()],
        )

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.fortuna_service.stop()
        win32event.SetEvent(self.hWaitStop)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.main()

    def main(self):
        self.fortuna_service.start()
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FortunaWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FortunaWindowsService)
