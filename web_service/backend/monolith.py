import sys
import os
import threading
import time
import uvicorn
import webview
from fastapi.staticfiles import StaticFiles
from web_service.backend.main import app

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def capture_screenshot_with_playwright(url):
    """
    Use Playwright to capture a screenshot of the running Monolith.
    This runs AFTER the window opens, proving the app is alive.
    """
    output_path = os.environ.get("SCREENSHOT_PATH", "monolith-screenshot.png")
    try:
        from playwright.sync_api import sync_playwright

        print(f"[MONOLITH] 📸 Launching Playwright for screenshot...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print(f"[MONOLITH] Navigating to {url}...")
            page.goto(url, wait_until="networkidle", timeout=15000)

            time.sleep(2)

            page.screenshot(path=output_path, full_page=True)

            print(f"[MONOLITH] ✅ Screenshot saved to {output_path}")

            browser.close()
            return True

    except Exception as e:
        print(f"[MONOLITH] ❌ Screenshot failed: {e}")
        return False

def start_monolith():
    static_dir = resource_path("frontend_dist")
    if os.path.exists(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"[MONOLITH] ✅ Serving frontend from {static_dir}")
    else:
        print("[MONOLITH] ⚠️  WARNING: Frontend dist not found. API only mode.")

    port = 8000
    url = f"http://127.0.0.1:{port}"

    def run_server():
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="error"
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print(f"[MONOLITH] 🚀 Backend server starting on {url}")

    time.sleep(2)

    print("[MONOLITH] 🪟 Opening native window...")
    webview.create_window('Fortuna Faucet (Monolith)', url, width=1280, height=800)

    screenshot_thread = threading.Thread(
        target=capture_screenshot_with_playwright,
        args=(url,),
        daemon=True
    )
    screenshot_thread.start()

    webview.start()

if __name__ == '__main__':
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()

    start_monolith()