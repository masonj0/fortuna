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

def capture_screenshot_with_playwright(url, output_path="monolith-screenshot.png"):
    """
    Use Playwright to capture a screenshot of the running Monolith.
    This runs AFTER the window opens, proving the app is alive.
    """
    try:
        from playwright.sync_api import sync_playwright

        print(f"[MONOLITH] 📸 Launching Playwright for screenshot...")

        with sync_playwright() as p:
            # Use chromium browser
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Wait for the page to load
            print(f"[MONOLITH] Navigating to {url}...")
            page.goto(url, wait_until="networkidle", timeout=15000)

            # Give it a moment to render
            time.sleep(2)

            # Capture the screenshot
            page.screenshot(path=output_path, full_page=True)

            print(f"[MONOLITH] ✅ Screenshot saved to {output_path}")

            browser.close()
            return True

    except Exception as e:
        print(f"[MONOLITH] ❌ Screenshot failed: {e}")
        return False

def start_monolith():
    # 1. Mount the bundled Frontend (built by React)
    static_dir = resource_path("frontend_dist")
    if os.path.exists(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"[MONOLITH] ✅ Serving frontend from {static_dir}")
    else:
        print("[MONOLITH] ⚠️  WARNING: Frontend dist not found. API only mode.")

    # 2. Start the Server in a background thread
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

    # Wait for server to be ready
    time.sleep(2)

    # 3. Launch the Native Window
    print("[MONOLITH] 🪟 Opening native window...")
    webview.create_window('Fortuna Faucet (Monolith)', url)

    # 4. Capture screenshot in background (doesn't block the window)
    screenshot_thread = threading.Thread(
        target=capture_screenshot_with_playwright,
        args=(url,),
        daemon=True
    )
    screenshot_thread.start()

    # Start the webview (blocking)
    webview.start()

if __name__ == '__main__':
    # Ensure PyInstaller multiprocessing works
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()

    start_monolith()