# verify_connection.py

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# --- Configuration ---
LOG_LEVEL = logging.INFO
# Set paths relative to the script's location
SCRIPT_DIR = Path(__file__).parent.resolve()
SCREENSHOT_DIR = SCRIPT_DIR / "verification"
FRONTEND_LOG_PATH = SCRIPT_DIR / "frontend.log"
BACKEND_LOG_PATH = SCRIPT_DIR / "backend.log"
FRONTEND_DIR = SCRIPT_DIR / "web_platform" / "frontend"
BACKEND_DIR = SCRIPT_DIR / "python_service"
BACKEND_ENTRYPOINT = BACKEND_DIR / "api.py"

# --- Setup Logging ---
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def start_backend():
    """Starts the FastAPI backend as a background process."""
    logging.info("Starting backend server...")
    # Ensure environment is set up for backend
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(SCRIPT_DIR)
    backend_env["API_KEY"] = "a_secure_test_api_key_that_is_long_enough"
    backend_env["ALLOWED_ORIGINS"] = '["http://localhost:3000", "http://127.0.0.1:3000"]'

    # Use shell=True for Windows compatibility if needed, but separate args is better
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "python_service.api:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=SCRIPT_DIR,
            stdout=open(BACKEND_LOG_PATH, "w"),
            stderr=subprocess.STDOUT,
            env=backend_env,
        )
        logging.info(f"Backend process started with PID: {process.pid}")
        # Give the server a moment to initialize
        time.sleep(5)
        return process
    except FileNotFoundError:
        logging.error(
            "uvicorn command not found. Make sure it's installed in the environment."
        )
        return None
    except Exception as e:
        logging.error(f"Failed to start backend: {e}", exc_info=True)
        return None


def start_frontend():
    """Starts the Next.js frontend dev server as a background process."""
    logging.info("Starting frontend development server...")
    try:
        # Check for node_modules and run npm install if not present
        if not (FRONTEND_DIR / "node_modules").exists():
            logging.info("node_modules not found. Running 'npm install'...")
            install_process = subprocess.run(
                ["npm", "install"],
                cwd=FRONTEND_DIR,
                check=True,
                capture_output=True,
                text=True,
            )
            logging.info(install_process.stdout)
            if install_process.returncode != 0:
                logging.error("npm install failed!")
                logging.error(install_process.stderr)
                return None

        # Start the dev server
        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=FRONTEND_DIR,
            stdout=open(FRONTEND_LOG_PATH, "w"),
            stderr=subprocess.STDOUT,
        )
        logging.info(f"Frontend process started with PID: {process.pid}")
        return process
    except FileNotFoundError:
        logging.error(
            "npm command not found. Make sure Node.js and npm are installed and in the PATH."
        )
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"npm install failed: {e.stderr}")
        return None
    except Exception as e:
        logging.error(f"Failed to start frontend: {e}", exc_info=True)
        return None


def get_frontend_port_from_logs(log_path: Path, timeout: int = 30) -> int:
    """Parses the frontend log file to find the port the dev server is running on."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if log_path.exists():
                with open(log_path, "r") as f:
                    for line in f:
                        if "Local:" in line and "http://localhost:" in line:
                            port_str = line.split("http://localhost:")[1].strip()
                            if port_str.isdigit():
                                port = int(port_str)
                                logging.info(f"Detected frontend port: {port}")
                                return port
        except Exception as e:
            logging.warning(f"Could not read frontend log yet, retrying... Error: {e}")
        time.sleep(1)
    logging.error(f"Could not determine frontend port after {timeout} seconds.")
    return 3000 # Fallback

def verify_connection():
    """
    Uses Playwright to verify the frontend can connect to the backend.
    Captures a screenshot for visual confirmation.
    """
    backend_process = None
    frontend_process = None
    success = False

    try:
        backend_process = start_backend()
        if not backend_process or backend_process.poll() is not None:
            logging.error("Backend failed to start or crashed.")
            return

        frontend_process = start_frontend()
        if not frontend_process or frontend_process.poll() is not None:
            logging.error("Frontend failed to start or crashed.")
            return

        logging.info("Waiting for frontend to be ready and getting port...")
        port = get_frontend_port_from_logs(FRONTEND_LOG_PATH)


        with sync_playwright() as p:
            logging.info("Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            logging.info(f"Navigating to frontend URL at port {port}...")
            page.goto(f"http://localhost:{port}")

            # Wait for a specific element that indicates a successful connection
            # or a definitive disconnected state.
            logging.info("Waiting for connection status indicator...")
            try:
                # Wait up to 30 seconds for either a 'Connected' or 'Failed' state
                page.wait_for_selector(
                    'text=/Connecting...|Connected|Connection Failed/',
                    timeout=30000
                )

                # Check the current status
                connection_status = page.locator('//button[contains(@class, "rounded-full")]').inner_text()
                logging.info(f"Connection status found: {connection_status}")
                if "Connected" in connection_status:
                    logging.info("Successfully connected to the backend.")
                    success = True
                else:
                    logging.error(f"Frontend indicated a connection failure: {connection_status}")


            except Exception as e:
                logging.error(f"Failed to find connection status indicator: {e}", exc_info=True)

            logging.info("Capturing screenshot...")
            SCREENSHOT_DIR.mkdir(exist_ok=True)
            screenshot_path = SCREENSHOT_DIR / "debug_screenshot.png"
            page.screenshot(path=str(screenshot_path))
            logging.info(f"Screenshot saved to {screenshot_path}")

            browser.close()

    finally:
        logging.info("Cleaning up processes...")
        if frontend_process and frontend_process.poll() is None:
            logging.info(f"Terminating frontend process {frontend_process.pid}")
            frontend_process.terminate()
            frontend_process.wait()
        if backend_process and backend_process.poll() is None:
            logging.info(f"Terminating backend process {backend_process.pid}")
            backend_process.terminate()
            backend_process.wait()
        logging.info("Cleanup complete.")
        # Exit with success or failure code
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    verify_connection()
