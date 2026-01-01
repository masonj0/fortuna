import sys
import os
import threading
import time
import uvicorn
import webview
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 1. Define the Monolith App directly (Decoupled from main.py)
app = FastAPI(title="Fortuna Monolith")

# Add CORS to allow the frontend to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Try to import existing routers (Optional)
try:
    # Attempt to import the API router from the backend package
    # Adjust this import path based on your actual structure if needed
    from web_service.backend.api import router as api_router
    app.include_router(api_router, prefix="/api")
    print("[MONOLITH] ✅ Loaded API routers")
except ImportError as e:
    print(f"[MONOLITH] ⚠️ Could not load API routers: {e}")
    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "monolith_fallback", "error": str(e)}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def capture_screenshot_with_playwright(url):
    """
    Use Playwright to capture a screenshot of the running Monolith.
    This runs AFTER the window opens, proving the app is alive.
    """
    screenshot_env_var = os.environ.get("SCREENSHOT_PATH")
    output_path = screenshot_env_var or "monolith-screenshot.png"

    print("--- Paparazzi Diagnostics ---")
    print(f"SCREENSHOT_PATH env var: {screenshot_env_var}")
    print(f"Final output path: {output_path}")
    print(f"Target URL: {url}")
    print("-----------------------------")

    try:
        from playwright.sync_api import sync_playwright

        print("[MONOLITH] 📸 Launching Playwright for screenshot...")

        with sync_playwright() as p:
            print("[Playwright] Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print(f"[Playwright] Navigating to {url}...")
            page.goto(url, wait_until="networkidle", timeout=15000)

            print("[Playwright] Waiting for 2 seconds...")
            time.sleep(2)

            print(f"[Playwright] Taking screenshot to {output_path}...")
            page.screenshot(path=output_path, full_page=True)

            print(f"[MONOLITH] ✅ Screenshot saved to {output_path}")

            browser.close()
            print("[Playwright] Browser closed.")
            return True

    except ImportError as e:
        print(f"[MONOLITH] ❌ Screenshot failed: Playwright not installed? {e}")
        return False
    except Exception as e:
        print(f"[MONOLITH] ❌ Screenshot failed with an unexpected error: {e}")
        # Also print traceback for more details
        import traceback
        traceback.print_exc()
        return False

def start_monolith():
    # 3. Mount the bundled Frontend
    static_dir = resource_path("frontend_dist")
    if os.path.exists(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"[MONOLITH] ✅ Serving frontend from {static_dir}")
    else:
        print(f"[MONOLITH] ❌ Frontend dist not found at {static_dir}")

    # 4. Start Server & Window
    port = 8000
    url = f"http://127.0.0.1:{port}"

    def run_server():
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info"
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    time.sleep(2)

    webview.create_window('Fortuna Faucet', url, width=1280, height=800)

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