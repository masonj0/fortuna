import subprocess
import sys
import os
import time
import json
from datetime import datetime
import requests
import shutil

# --- Configuration ---
PYTHON_VERSION = "3.11"
BACKEND_DIR = "web_service/backend"
SPEC_FILE = "fortuna-linux-report.spec"
SERVICE_PORT = 8000
API_KEY = "a_secure_test_api_key_that_is_long_enough"

# --- Helper Functions ---
def print_step(msg):
    print(f"\n🚀 {msg}")

def print_success(msg):
    print(f"   ✅ {msg}")

def print_warn(msg):
    print(f"   ⚠️  {msg}")

def print_fail(msg):
    print(f"   ❌ {msg}")
    sys.exit(1)

def run_command(command):
    try:
        # Use sys.executable to ensure we're using the same python
        process = subprocess.run([sys.executable, "-m"] + command, check=True, capture_output=True, text=True)
        print(process.stdout)
    except subprocess.CalledProcessError as e:
        print_fail(f"Command failed: {' '.join(command)}\n{e.stderr}")

# --- Main Execution ---
backend_process = None
try:
    # 1. Environment Setup & Dependency Installation
    print_step("Preparing environment...")
    try:
        py_ver = subprocess.check_output([sys.executable, "--version"], text=True).strip()
        if PYTHON_VERSION not in py_ver:
            print_warn(f"Python version mismatch. Expected {PYTHON_VERSION}, found {py_ver}.")
        print_success(f"Found Python: {py_ver}")
    except Exception as e:
        print_fail(f"Python not found. Error: {e}")

    print_step("Installing dependencies...")
    run_command(["pip", "install", "--upgrade", "pip"])
    run_command(["pip", "install", "-r", f"{BACKEND_DIR}/requirements.txt"])
    run_command(["pip", "install", "pyinstaller==6.6.0"])
    # pywin32 is not available on Linux, so we skip it. The spec file is configured for a cross-platform build.
    print_success("All Python dependencies are installed.")

    # 2. Build the Backend Executable
    print_step("Building backend executable with PyInstaller...")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    os.makedirs(os.path.join(BACKEND_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(BACKEND_DIR, "json"), exist_ok=True)
    os.makedirs(os.path.join(BACKEND_DIR, "logs"), exist_ok=True)

    run_command(["PyInstaller", "--noconfirm", "--clean", SPEC_FILE])
    print_success("Backend executable built successfully.")

    # 3. Launch the Backend Service
    print_step("Launching backend service...")
    exe_path = os.path.abspath("dist/fortuna-webservice/fortuna-webservice")
    if not os.path.exists(exe_path):
        print_fail(f"Could not find the built executable at {exe_path}.")

    exe_dir = os.path.dirname(exe_path)
    os.makedirs(os.path.join(exe_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(exe_dir, "json"), exist_ok=True)
    os.makedirs(os.path.join(exe_dir, "logs"), exist_ok=True)
    print_success(f"Created runtime directories in {exe_dir}.")

    stdout_log = open('backend_stdout.log', 'w')
    stderr_log = open('backend_stderr.log', 'w')
    backend_process = subprocess.Popen([exe_path], stdout=stdout_log, stderr=stderr_log)
    print_success(f"Backend service is starting in the background (PID: {backend_process.pid}).")

    # 4. Health Check, API Query, and Data Injection
    print_step("Waiting for service to become healthy...")
    health_url = f"http://localhost:{SERVICE_PORT}/health"
    max_retries = 60
    retry_delay = 2  # seconds

    for i in range(max_retries):
        try:
            response = requests.get(health_url, timeout=2)
            if response.status_code == 200:
                print_success("Service is healthy and responding.")
                break
            elif response.status_code == 503:
                print(f"   ... service is starting up (503), waiting ({i+1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print_warn(f"   ... received unexpected status {response.status_code}, retrying ({i+1}/{max_retries})")
                time.sleep(retry_delay)
        except requests.exceptions.RequestException:
            print(f"   ... waiting for connection ({i+1}/{max_retries})")
            time.sleep(retry_delay)
    else:
        print_fail("Service failed to start or become healthy within the timeout period.")

    print_step("Querying API for deluxe race data...")
    races_url = f"http://localhost:{SERVICE_PORT}/api/races"
    headers = {"X-API-Key": API_KEY}
    try:
        api_response = requests.get(races_url, headers=headers).json()
        print_success(f"Successfully fetched deluxe race data for {len(api_response.get('races', []))} races.")
    except Exception as e:
        print_fail(f"Failed to query the API. Error: {e}")

    print_step("Injecting data into HTML template...")
    template_path = "scripts/templates/race_report_template.html"
    output_path = "race-report.html"

    if not os.path.exists(template_path):
        print_fail(f"HTML template not found at {template_path}.")

    with open(template_path, "r") as f:
        template_content = f.read()

    json_for_injection = json.dumps(api_response, indent=4)
    final_html = template_content.replace("__RACE_DATA_PLACEHOLDER__", json_for_injection)

    with open(output_path, "w") as f:
        f.write(final_html)
    print_success(f"Deluxe race report generated at {output_path}.")

finally:
    # 5. Cleanup
    print_step("Cleaning up...")
    if backend_process:
        try:
            backend_process.terminate()
            backend_process.wait(timeout=5)
            print_success(f"Backend service (PID: {backend_process.pid}) stopped.")
        except (subprocess.TimeoutExpired, PermissionError) as e:
            print_warn(f"Could not stop backend service (PID: {backend_process.pid}). It may need to be stopped manually. Error: {e}")
