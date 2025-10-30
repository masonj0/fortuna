# python_service/notifications.py

import sys

import structlog

log = structlog.get_logger(__name__)


def send_toast(title: str, message: str):
    """
    Sends a desktop notification. This function is platform-aware and will only
    attempt to send a toast on Windows. On other operating systems, it will
    log the notification content.
    """
    if sys.platform == "win32":
        try:
            from windows_toasts import Toast
            from windows_toasts import WindowsToaster

            toaster = WindowsToaster(title)
            new_toast = Toast()
            new_toast.text_fields = [message]
            toaster.show_toast(new_toast)
            log.info("Sent Windows toast notification.", title=title, message=message)
        except ImportError:
            log.warning(
                "windows_toasts library not found, skipping notification.",
                recommendation="Install with: pip install windows-toasts",
            )
        except Exception:
            log.error("Failed to send Windows toast notification.", exc_info=True)
    else:
        log.info(
            "Skipping toast notification on non-Windows platform.",
            platform=sys.platform,
            title=title,
            message=message,
        )
