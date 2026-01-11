#!/usr/bin/env python3
"""
Fortuna Faucet - Unified Python Launcher
Alternative to EXE/MSI: Runs the entire application (frontend + backend) using pure Python
Suitable for: Development, testing, alternative deployment, or environments without installers

Usage:
    python fortuna_launcher.py              # Runs with default settings (opens browser)
    python fortuna_launcher.py --dev        # Dev mode with hot reload
    python fortuna_launcher.py --port 8080  # Custom port
    python fortuna_launcher.py --no-open    # Don't open browser automatically
"""

import sys
import os
import logging
import subprocess
import threading
import time
import json
import webbrowser
import argparse
import socket
from pathlib import Path
from typing import Optional
from contextlib import suppress
from datetime import datetime

# ====================================================================
# CONFIGURATION
# ====================================================================
# This is a trivial change to trigger the CI workflow.
APP_NAME = "Fortuna Faucet"
APP_VERSION = "2.0.0"
DEFAULT_PORT = 8000
DEFAULT_HOST = "127.0.0.1"

# ====================================================================
# SETUP PATHS
# ====================================================================
PROJECT_ROOT = Path(__file__).parent.absolute()
BACKEND_DIR = PROJECT_ROOT / "web_service" / "backend"
FRONTEND_DIR = PROJECT_ROOT / "web_platform" / "frontend"
VENV_DIR = PROJECT_ROOT / ".venv"
LOG_DIR = PROJECT_ROOT / "logs"

# Create directories
LOG_DIR.mkdir(exist_ok=True)

# ====================================================================
# FANCY COLORS & FORMATTING
# ====================================================================
class Colors:
    """Terminal color codes for friendly output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def is_windows():
    """Check if running on Windows"""
    return sys.platform.startswith('win')

# Disable colors on Windows if not supported
if is_windows():
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        # If colors fail on Windows, disable them
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, '')

# ====================================================================
# LOGGING SETUP WITH FANCY OUTPUT
# ====================================================================
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""

    COLORS = {
        'DEBUG': Colors.OKCYAN,
        'INFO': Colors.OKBLUE,
        'WARNING': Colors.WARNING,
        'ERROR': Colors.FAIL,
        'CRITICAL': Colors.FAIL + Colors.BOLD,
    }

    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Colors.ENDC}"
        return super().format(record)

def setup_logging():
    """Configure logging with both file and console output"""
    log_file = LOG_DIR / f"fortuna_launcher_{time.strftime('%Y%m%d_%H%M%S')}.log"

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = ColoredFormatter(
        "[%(levelname)-8s] %(asctime)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)

    # File handler without colors
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_formatter = logging.Formatter(
        "[%(levelname)-8s] %(asctime)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler, file_handler]
    )

    logger = logging.getLogger("fortuna")
    return logger

logger = setup_logging()

# ====================================================================
# FANCY BANNER
# ====================================================================
def print_banner():
    """Print a fancy welcome banner"""
    banner = f"""
{Colors.BOLD}{Colors.OKGREEN}
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║              🐴  {APP_NAME} v{APP_VERSION}  🐴              ║
║          Unified Python Launcher (No EXE/MSI Needed)          ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)

def print_success(msg: str, icon: str = "✓"):
    """Print a success message"""
    print(f"{Colors.OKGREEN}{icon}{Colors.ENDC} {msg}")

def print_warning(msg: str, icon: str = "⚠"):
    """Print a warning message"""
    print(f"{Colors.WARNING}{icon}{Colors.ENDC} {msg}")

def print_error(msg: str, icon: str = "✗"):
    """Print an error message"""
    print(f"{Colors.FAIL}{icon}{Colors.ENDC} {msg}")

def print_info(msg: str, icon: str = "ℹ"):
    """Print an info message"""
    print(f"{Colors.OKBLUE}{icon}{Colors.ENDC} {msg}")

# ====================================================================
# ENVIRONMENT DETECTION & VALIDATION
# ====================================================================
class EnvironmentManager:
    """Manages Python environment and dependencies"""

    def __init__(self):
        self.is_venv = self._detect_venv()
        self.python_exe = sys.executable
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _detect_venv(self) -> bool:
        """Check if we're running in a virtual environment"""
        return (hasattr(sys, 'real_prefix') or
                (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

    def validate_environment(self) -> bool:
        """Validate that required directories and files exist"""
        print_info("Validating environment...")

        critical_paths = {
            "Backend directory": BACKEND_DIR,
            "Frontend directory": FRONTEND_DIR,
            "Backend requirements": BACKEND_DIR / "requirements.txt",
            "Next.js config": FRONTEND_DIR / "package.json",
        }

        all_valid = True
        for name, path in critical_paths.items():
            exists = path.exists()
            if exists:
                print_success(f"{name}", icon="  ")
            else:
                print_error(f"{name}: {path}", icon="  ")
                all_valid = False

        print_info(f"Python: {self.python_version}")
        if self.is_venv:
            print_success("Running in virtual environment")
        else:
            print_warning("Not running in a virtual environment (recommended)")

        if all_valid:
            print_success("Environment validation passed")
        else:
            print_error("Critical paths are missing!")

        return all_valid

    def install_dependencies(self, force: bool = False) -> bool:
        """Install backend dependencies"""
        print_info("Checking Python dependencies...")

        requirements_file = BACKEND_DIR / "requirements.txt"

        try:
            # Check if dependencies are already installed
            if not force:
                try:
                    import fastapi
                    import uvicorn
                    print_success("Core dependencies already installed")
                    return True
                except ImportError:
                    pass

            print_info(f"Installing dependencies (this may take a minute)...")
            result = subprocess.run(
                [self.python_exe, "-m", "pip", "install", "-q", "-r", str(requirements_file)],
                capture_output=True,
                text=True,
                cwd=str(BACKEND_DIR)
            )

            if result.returncode != 0:
                print_error(f"Dependency installation failed:\n{result.stderr}")
                return False

            print_success("Dependencies installed successfully")
            return True

        except Exception as e:
            print_error(f"Dependency installation error: {e}")
            return False

# ====================================================================
# FRONTEND BUILDER
# ====================================================================
class FrontendBuilder:
    """Manages Next.js frontend build"""

    def __init__(self):
        self.npm_available = self._check_npm()
        self.node_available = self._check_node()
        self.build_dir = FRONTEND_DIR / "out"

    def _check_npm(self) -> bool:
        """Check if npm is available"""
        try:
            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _check_node(self) -> bool:
        """Check if Node.js is available"""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def build(self, dev_mode: bool = False) -> bool:
        """Build the Next.js frontend"""
        if not self.npm_available or not self.node_available:
            print_warning("Node.js/npm not found - frontend will not be rebuilt")
            print_info("To fix: Install Node.js from https://nodejs.org/")
            if self.build_dir.exists():
                print_success("Using existing frontend build")
                return True
            return False

        print_info("Building frontend...")

        try:
            # Install npm dependencies
            print_info("Installing npm dependencies...")
            result = subprocess.run(
                ["npm", "ci", "--silent"],
                cwd=str(FRONTEND_DIR),
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                print_error(f"npm ci failed:\n{result.stderr}")
                return False

            # Build frontend
            print_info("Running Next.js build...")
            build_cmd = "dev" if dev_mode else "build"
            result = subprocess.run(
                ["npm", "run", build_cmd, "--silent"],
                cwd=str(FRONTEND_DIR),
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode != 0:
                print_error(f"Frontend build failed:\n{result.stderr}")
                return False

            print_success(f"Frontend build complete")
            return True

        except subprocess.TimeoutExpired:
            print_error("Frontend build timed out")
            return False
        except Exception as e:
            print_error(f"Frontend build error: {e}")
            return False

# ====================================================================
# BACKEND SERVER
# ====================================================================
class BackendServer:
    """Manages the FastAPI backend server"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.logs = []
        self.is_ready = False
        self.startup_time = None

    def start(self) -> bool:
        """Start the backend server"""
        print_info(f"Starting backend server on {self.host}:{self.port}...")
        self.startup_time = time.time()

        try:
            # Change to backend directory and run uvicorn
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    "-m", "uvicorn",
                    "web_service.backend.main:app",
                    "--host", self.host,
                    "--port", str(self.port),
                    "--log-level", "warning"
                ],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Monitor logs in background
            threading.Thread(target=self._log_monitor, daemon=True).start()

            # Wait for server to be ready
            self.is_ready = self._wait_for_ready()

            if self.is_ready:
                elapsed = time.time() - self.startup_time
                print_success(f"Backend ready in {elapsed:.1f}s at http://{self.host}:{self.port}")
                return True
            else:
                print_error("Backend failed to start (health check failed)")
                self.stop()
                return False

        except Exception as e:
            print_error(f"Failed to start backend: {e}")
            return False

    def _log_monitor(self):
        """Monitor backend logs"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    line = line.rstrip()
                    self.logs.append(line)
                    logger.debug(f"[Backend] {line}")
        except:
            pass

    def _wait_for_ready(self, max_retries: int = 30) -> bool:
        """Wait for backend to respond to health check"""
        for attempt in range(max_retries):
            try:
                sock = socket.create_connection((self.host, self.port), timeout=2)
                sock.close()
                return True
            except:
                if attempt < max_retries - 1:
                    time.sleep(1)

        return False

    def stop(self):
        """Stop the backend server"""
        if self.process and not self.process.poll():
            print_info("Stopping backend server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            print_success("Backend stopped")

# ====================================================================
# BROWSER LAUNCHER (WITH RETRY LOGIC)
# ====================================================================
class BrowserLauncher:
    """Manages opening the application in a web browser"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.url = f"http://{host}:{port}"
        self.host = host
        self.port = port

    def open(self) -> bool:
        """Open the application in the default browser with retry logic"""
        try:
            # Add a small delay to ensure backend is fully ready
            time.sleep(0.5)

            print_info(f"Opening browser at {self.url}...")
            webbrowser.open(self.url)
            print_success("Browser opened!")
            return True
        except Exception as e:
            print_warning(f"Could not open browser automatically: {e}")
            print_info(f"Please manually open: {Colors.BOLD}{self.url}{Colors.ENDC}")
            return False

# ====================================================================
# MAIN APPLICATION
# ====================================================================
class FortunaLauncher:
    """Main application orchestrator"""

    def __init__(self, args):
        self.args = args
        self.env = EnvironmentManager()
        self.backend: Optional[BackendServer] = None
        self.frontend: Optional[FrontendBuilder] = None

    def run(self) -> int:
        """Run the complete application"""
        ui_available = True  # Assume UI is available by default
        try:
            print_banner()

            # Validate environment
            if not self.env.validate_environment():
                print_error("Environment validation failed!")
                return 1

            print()  # Blank line for readability

            # Install dependencies
            if not self.env.install_dependencies():
                print_error("Dependency installation failed!")
                return 1

            print()  # Blank line for readability

            # Build frontend
            if self.args.no_build:
                print_info("Skipping frontend build (as requested)")
                if not (FRONTEND_DIR / "out").exists():
                    print_warning("No existing frontend build found. UI will be unavailable.")
                    ui_available = False
            else:
                self.frontend = FrontendBuilder()
                if not self.frontend.build(dev_mode=self.args.dev):
                    if self.frontend.build_dir.exists():
                        print_warning("Using existing frontend build (new build failed)")
                    else:
                        print_warning("Frontend build failed and no existing build found! UI will be unavailable.")
                        ui_available = False

            print()  # Blank line for readability

            # Start backend
            self.backend = BackendServer(
                host=DEFAULT_HOST,
                port=self.args.port
            )
            if not self.backend.start():
                print_error("Backend startup failed!")
                return 1

            print()  # Blank line for readability

            # Open browser (default unless --no-open)
            if ui_available:
                if not self.args.no_open:
                    browser = BrowserLauncher(DEFAULT_HOST, self.args.port)
                    browser.open()
                else:
                    print_info(f"Access the application at: {Colors.BOLD}http://{DEFAULT_HOST}:{self.args.port}{Colors.ENDC}")
            else:
                print_info("Frontend UI is not available.")
                print_info(f"Access the API documentation at: {Colors.BOLD}http://{DEFAULT_HOST}:{self.args.port}/api/docs{Colors.ENDC}")


            # Keep application running
            print()  # Blank line for readability
            print(f"{Colors.BOLD}{Colors.OKGREEN}")
            print("╔════════════════════════════════════════════════════════════════╗")
            if ui_available:
                print("║                    🎉 ALL SYSTEMS GO! 🎉                      ║")
                print(f"║                  {APP_NAME} is running!                   ║")
                print("║                                                                ║")
                print(f"║         Frontend UI: http://{DEFAULT_HOST}:{self.args.port:<7}                 ║")
            else:
                print("║               Backend ONLY - NO UI AVAILABLE                ║")
                print(f"║                  {APP_NAME} is running!                   ║")

            print(f"║         API Docs:    http://{DEFAULT_HOST}:{self.args.port:<7}/api/docs         ║")
            print("║                                                                ║")
            print("║                Press Ctrl+C to stop the server                 ║")
            print("╚════════════════════════════════════════════════════════════════╝")
            print(f"{Colors.ENDC}")
            print()

            # Wait for user interrupt
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print()
                print_info("Shutting down gracefully...")
                return 0

        except Exception as e:
            print_error(f"Fatal error: {e}", icon="💥")
            logger.error(f"Fatal error:", exc_info=True)
            return 1
        finally:
            if self.backend:
                self.backend.stop()
            print()
            print_success("Goodbye! Thanks for using Fortuna Faucet 🐴")
            print()

# ====================================================================
# ENTRY POINT
# ====================================================================
def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - Unified Python Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.BOLD}Examples:{Colors.ENDC}
  python fortuna_launcher.py                    # Run (auto-opens browser)
  python fortuna_launcher.py --dev              # Dev mode with hot reload
  python fortuna_launcher.py --port 8080        # Custom port
  python fortuna_launcher.py --no-open          # Don't open browser
  python fortuna_launcher.py --no-build         # Skip frontend build

{Colors.BOLD}Features:{Colors.ENDC}
  ✓ Auto-opens browser on startup (disable with --no-open)
  ✓ Colored, friendly terminal output
  ✓ Auto-installs Python dependencies
  ✓ Automatic Next.js frontend build
  ✓ Comprehensive error messages
  ✓ Full logging to file
        """
    )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to run the server on (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode with hot reload"
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't automatically open browser on startup"
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip frontend build and use existing build"
    )

    args = parser.parse_args()

    launcher = FortunaLauncher(args)
    sys.exit(launcher.run())

if __name__ == "__main__":
    main()
