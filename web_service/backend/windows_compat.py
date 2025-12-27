"""
Windows Compatibility Utilities

CRITICAL: This module MUST be imported and called at the top of EVERY entry point
that uses asyncio or uvicorn in a PyInstaller bundle on Windows.

Without this fix, the asyncio event loop will fail to bind network ports, causing
silent failures where uvicorn reports "Application startup complete" but the
service is actually inaccessible.
"""

import sys


def setup_windows_event_loop():
    """
    Configure Windows event loop policy for PyInstaller bundles.

    This MUST be called BEFORE any asyncio or uvicorn initialization.

    Context:
    - PyInstaller bundles on Windows have a broken default event loop policy
    - The default policy (ProactorEventLoop) silently fails to bind ports
    - WindowsSelectorEventLoopPolicy is the only policy that works reliably

    This function is idempotent and safe to call multiple times.
    """
    if sys.platform == 'win32' and getattr(sys, 'frozen', False):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print('[BOOT] ✓ Applied WindowsSelectorEventLoopPolicy for PyInstaller',
              file=sys.stderr)
    else:
        # Not Windows or not frozen - no action needed
        pass
