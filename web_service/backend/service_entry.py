import sys
import win32serviceutil
import win32service
import win32event
import servicemanager
import ctypes

class FortunaService(win32serviceutil.ServiceFramework):
    _svc_name_ = "FortunaWebService"
    _svc_display_name_ = "Fortuna Web Service"
    _svc_description_ = "Background service for Fortuna Faucet"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        from main import run_server
        run_server()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Heuristic: If run with no arguments, check if we are in a service context.
        # If StartServiceCtrlDispatcher fails, we are likely being double-clicked by a user.
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(FortunaService)
            servicemanager.StartServiceCtrlDispatcher()
        except Exception:
            # 🚨 USER ALERT: Show a message box instead of failing silently
            ctypes.windll.user32.MessageBoxW(0,
                u"This is a background service.\\n\\nPlease install 'HatTrickFusion.msi' to set it up correctly.",
                u"Fortuna Service", 0x10)
    else:
        win32serviceutil.HandleCommandLine(FortunaService)