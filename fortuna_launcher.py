#!/usr/bin/env python3
"""
Fortuna Faucet - Enhanced Standalone Launcher for Windows 10 Home
No Docker, no special permissions, just pure Python magic
Run this file and your browser opens automatically with all the bells and whistles
"""

import sys
import os
import subprocess
import threading
import time
import webbrowser
import socket
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

# ====================================================================
# CONFIGURATION
# ====================================================================
APP_NAME = "Fortuna Faucet"
APP_VERSION = "3.1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
BACKEND_STARTUP_TIMEOUT = 15
HEALTH_CHECK_ATTEMPTS = 30
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# ====================================================================
# COLORS FOR WINDOWS CONSOLE
# ====================================================================
class Colors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

# Try to enable ANSI colors on Windows 10
try:
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except:
    pass

# ====================================================================
# LOGGING
# ====================================================================
class Logger:
    """Dual logging to console and file"""
    def __init__(self):
        self.log_file = LOG_DIR / f"fortuna_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    def write(self, level: str, message: str):
        """Write to both console and file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

logger = Logger()

# ====================================================================
# HELPER FUNCTIONS
# ====================================================================
def print_banner():
    """Print welcome banner"""
    banner = f"""
{Colors.BOLD}{Colors.OKGREEN}
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║              🐴  {APP_NAME} v{APP_VERSION}  🐴              ║
║         Enhanced Launcher - Windows 10 Home Ready         ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)

def print_success(msg: str, icon: str = "✓"):
    """Print success message"""
    output = f"{Colors.OKGREEN}{icon}{Colors.ENDC} {msg}"
    print(output)
    logger.write("SUCCESS", msg)

def print_warning(msg: str, icon: str = "⚠"):
    """Print warning message"""
    output = f"{Colors.WARNING}{icon}{Colors.ENDC} {msg}"
    print(output)
    logger.write("WARNING", msg)

def print_error(msg: str, icon: str = "✗"):
    """Print error message"""
    output = f"{Colors.FAIL}{icon}{Colors.ENDC} {msg}"
    print(output)
    logger.write("ERROR", msg)

def print_info(msg: str, icon: str = "ℹ"):
    """Print info message"""
    output = f"{Colors.OKBLUE}{icon}{Colors.ENDC} {msg}"
    print(output)
    logger.write("INFO", msg)

def print_step(step_num: int, total: int, msg: str):
    """Print step counter"""
    output = f"\n{Colors.BOLD}[{step_num}/{total}] {msg}{Colors.ENDC}"
    print(output)
    logger.write("STEP", f"[{step_num}/{total}] {msg}")

def print_section(title: str):
    """Print section divider"""
    output = f"\n{Colors.BOLD}{Colors.OKCYAN}{'─' * 60}{Colors.ENDC}"
    print(output)
    print(f"{Colors.BOLD}{Colors.OKCYAN}{title}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKCYAN}{'─' * 60}{Colors.ENDC}\n")

def print_step(step_num: int, total: int, msg: str):
    """Print step counter"""
    print(f"\n{Colors.BOLD}[{step_num}/{total}] {msg}{Colors.ENDC}")

# ====================================================================
# ENVIRONMENT CHECKS
# ====================================================================
def check_python_version() -> bool:
    """Check if Python version is compatible"""
    if sys.version_info < (3, 10):
        print_error(f"Python 3.10+ required, you have {sys.version_info.major}.{sys.version_info.minor}")
        return False
    print_success(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def check_project_structure() -> bool:
    """Check if we're in the right directory"""
    required_dirs = [
        "web_service/backend",
        "web_platform/frontend"
    ]
    required_files = [
        "web_service/backend/requirements.txt",
        "web_platform/frontend/package.json"
    ]

    print_info("Checking project structure...")
    all_good = True
    for d in required_dirs:
        if Path(d).exists():
            print_success(f"Found: {d}")
        else:
            print_error(f"Missing: {d}")
            all_good = False

    for f in required_files:
        if Path(f).exists():
            print_success(f"Found: {f}")
        else:
            print_error(f"Missing: {f}")
            all_good = False

    return all_good

def check_port_available(port: int) -> bool:
    """Check if port is available"""
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=1)
        sock.close()
        print_error(f"Port {port} is already in use by another application")
        return False
    except (socket.timeout, ConnectionRefusedError, OSError):
        print_success(f"Port {port} is available")
        return True

# ====================================================================
# DEPENDENCY CHECK & INSTALL
# ====================================================================
def check_and_install_dependencies() -> bool:
    """Check if dependencies are installed, install if needed"""
    print_info("Checking Python dependencies...")

    required_packages = {
        "fastapi": "FastAPI web framework",
        "uvicorn": "ASGI server",
        "pydantic": "Data validation",
    }

    missing = []
    for package, description in required_packages.items():
        try:
            __import__(package)
            print_success(f"{description} (installed)")
        except ImportError:
            print_warning(f"{description} (NOT installed)")
            missing.append(package)

    if not missing:
        print_success("All core dependencies satisfied!")
        return True

    print()
    print_info(f"Installing {len(missing)} missing package(s)...")
    print_info("This may take 2-3 minutes on first run...")
    print()

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip"],
            check=True,
            capture_output=True,
            timeout=120
        )

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q"] + missing,
            check=True,
            capture_output=True,
            timeout=300
        )
        print_success("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        print_info("Try running manually in PowerShell:")
        print(f"  python -m pip install -r web_service/backend/requirements.txt")
        logger.write("ERROR", f"Dependency installation failed: {e}")
        return False
    except subprocess.TimeoutExpired:
        print_error("Installation timed out (took too long)")
        return False

# ====================================================================
# FRONTEND BUILD
# ====================================================================
def build_frontend() -> bool:
    """Build Next.js frontend if needed"""
    frontend_dir = Path("web_platform/frontend")
    build_dir = frontend_dir / "out"

    if build_dir.exists() and (build_dir / "index.html").exists():
        print_success("Frontend already built")
        return True

    print_info("Frontend build required...")

    # Check for Node.js
    try:
        subprocess.run(["npm", "--version"], capture_output=True, timeout=5, check=True)
    except:
        print_warning("Node.js not found - frontend may not load properly")
        print_info("To fix: Install Node.js from https://nodejs.org/")
        logger.write("WARNING", "Node.js not found for frontend build")
        return True

    print_info("Building frontend (this takes ~30 seconds)...")
    print_info("(Progress shown in logs)")

    try:
        subprocess.run(
            ["npm", "ci"],
            cwd=str(frontend_dir),
            capture_output=True,
            timeout=120,
            check=True
        )
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(frontend_dir),
            capture_output=True,
            timeout=180,
            check=True
        )
        print_success("Frontend built successfully")
        return True
    except subprocess.TimeoutExpired:
        print_warning("Frontend build timed out, continuing anyway...")
        logger.write("WARNING", "Frontend build timed out")
        return True
    except subprocess.CalledProcessError as e:
        print_warning(f"Frontend build failed: {e}")
        logger.write("WARNING", f"Frontend build failed: {e}")
        return True
    except Exception as e:
        print_warning(f"Frontend build error: {e}")
        logger.write("WARNING", f"Frontend build error: {e}")
        return True

# ====================================================================
# BACKEND SERVER
# ====================================================================
def start_backend() -> Optional[subprocess.Popen]:
    """Start the FastAPI backend server"""
    print_info("Starting FastAPI server...")

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m", "uvicorn",
                "web_service.backend.main:app",
                "--host", DEFAULT_HOST,
                "--port", str(DEFAULT_PORT),
                "--log-level", "info"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Give it a moment to start
        time.sleep(1)

        if process.poll() is not None:
            # Process exited already
            stdout, stderr = process.communicate()
            print_error(f"Backend failed to start: {stderr[:200]}")
            logger.write("ERROR", f"Backend startup failed: {stderr}")
            return None

        print_success("Backend server started")
        logger.write("SUCCESS", "Backend server started successfully")
        return process

    except Exception as e:
        print_error(f"Failed to start backend: {e}")
        logger.write("ERROR", f"Backend start exception: {e}")
        return None

def wait_for_backend_ready(max_retries: int = HEALTH_CHECK_ATTEMPTS) -> bool:
    """Wait for backend to respond to health check"""
    import urllib.request
    import urllib.error

    print_info("Waiting for backend to be ready...")

    for attempt in range(max_retries):
        try:
            response = urllib.request.urlopen(
                f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/api/health",
                timeout=2
            )
            if response.status == 200:
                elapsed = attempt + 1
                print_success(f"Backend ready in {elapsed} second(s)")
                logger.write("SUCCESS", f"Backend health check passed in {elapsed}s")
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            if attempt < max_retries - 1:
                time.sleep(1)

    print_error("Backend did not respond after 30 seconds")
    logger.write("ERROR", "Backend health check failed - no response after 30s")
    return False

# ====================================================================
# BROWSER LAUNCHER
# ====================================================================
def open_browser():
    """Open browser to the application"""
    url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    try:
        print_info(f"Opening browser at {url}...")
        webbrowser.open(url)
        time.sleep(1)  # Give browser time to open
        print_success("Browser opened!")
        logger.write("SUCCESS", f"Browser opened at {url}")
    except Exception as e:
        print_warning(f"Could not open browser automatically: {e}")
        print_info(f"Please manually open: {url}")
        logger.write("WARNING", f"Browser auto-open failed: {e}")

# ====================================================================
# SYSTEM INFO
# ====================================================================
def print_system_info():
    """Print system information"""
    print_section("System Information")
    print_success(f"Python: {sys.version.split()[0]}")
    print_success(f"Platform: {sys.platform}")
    print_success(f"Current Directory: {Path.cwd()}")
    print_success(f"Log Directory: {LOG_DIR.absolute()}")
    print()

# ====================================================================
# MAIN APPLICATION
# ====================================================================
def main():
    """Main entry point"""
    print_banner()
    print_system_info()

    # Step 1: Environment validation
    print_step(1, 5, "Validating environment...")
    if not check_python_version():
        return 1
    if not check_project_structure():
        return 1
    if not check_port_available(DEFAULT_PORT):
        return 1
    print()

    # Step 2: Dependencies
    print_step(2, 5, "Installing dependencies...")
    if not check_and_install_dependencies():
        return 1
    print()

    # Step 3: Frontend build
    print_step(3, 5, "Building frontend...")
    build_frontend()
    print()

    # Step 4: Start backend
    print_step(4, 5, "Starting backend server...")
    backend_process = start_backend()
    if not backend_process:
        return 1

    if not wait_for_backend_ready():
        backend_process.terminate()
        logger.write("ERROR", "Application startup failed - health check timeout")
        return 1
    print()

    # Step 5: Open browser
    print_step(5, 5, "Launching browser...")
    open_browser()
    print()

    # Success!
    print(f"{Colors.BOLD}{Colors.OKGREEN}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                                                            ║")
    print("║          🎉  FORTUNA IS RUNNING!  🎉                     ║")
    print("║                                                            ║")
    print(f"║  Access your app at: http://{DEFAULT_HOST}:{DEFAULT_PORT:<5}                      ║")
    print("║                                                            ║")
    print(f"║  Log file: {LOG_DIR / 'fortuna_*.log':<40}  ║")
    print("║                                                            ║")
    print("║  Press Ctrl+C to stop the server                          ║")
    print("║                                                            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    print()

    # Keep running
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print()
        print_info("Shutting down gracefully...")
        backend_process.terminate()
        try:
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_process.kill()
        print_success("Fortuna stopped successfully")
        logger.write("SUCCESS", "Application stopped gracefully by user")
        return 0

if __name__ == "__main__":
    sys.exit(main())
