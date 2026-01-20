#!/usr/bin/env python
"""
Enhanced Fortuna Race Report Generator with Debugging

Provides detailed diagnostics to troubleshoot API authentication issues.
"""

import json
import os
import sys
import time
import subprocess
import requests
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8000"
HEALTH_ENDPOINT = f"{BASE_URL}/api/health"
API_ENDPOINT = f"{BASE_URL}/api/races/qualified/tiny_field_trifecta"
ALTERNATE_ENDPOINTS = [
    f"{BASE_URL}/api/races",
    f"{BASE_URL}/api/races/qualified",
    f"{BASE_URL}/api/races/today",
]
TEMPLATE_PATH = "scripts/templates/race_report_template.html"
OUTPUT_PATH = "race-report.html"
JSON_OUTPUT_PATH = "qualified_races.json"

# Timeouts
INITIAL_WAIT = 5
HEALTH_CHECK_TIMEOUT = 60
HEALTH_CHECK_INTERVAL = 5
API_QUERY_TIMEOUT = 30

# API Key
API_KEY = os.environ.get("API_KEY", "a_secure_test_api_key_that_is_long_enough")


def log(message, level="INFO"):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "DEBUG": "🔍"}
    print(f"[{timestamp}] {emoji.get(level, '•')} {message}")
    sys.stdout.flush()


def test_endpoint(url, headers=None, description="Endpoint"):
    """Test an endpoint and return detailed results."""
    log(f"Testing {description}: {url}", "DEBUG")

    try:
        response = requests.get(url, headers=headers, timeout=10)

        log(f"  Status: {response.status_code}", "DEBUG")

        if response.status_code == 200:
            try:
                data = response.json()
                log(f"  ✅ Success! Response preview: {str(data)[:100]}...", "SUCCESS")
                return True, response
            except json.JSONDecodeError:
                log(f"  ✅ Success (non-JSON): {response.text[:100]}...", "SUCCESS")
                return True, response
        elif response.status_code == 403:
            log(f"  ❌ 403 Forbidden - Check API key or authentication", "ERROR")
            log(f"  Response: {response.text[:200]}", "DEBUG")
            return False, response
        elif response.status_code == 404:
            log(f"  ⚠️ 404 Not Found - Endpoint doesn't exist", "WARNING")
            return False, response
        else:
            log(f"  ⚠️ Status {response.status_code}: {response.text[:200]}", "WARNING")
            return False, response

    except requests.exceptions.Timeout:
        log(f"  ❌ Timeout after 10 seconds", "ERROR")
        return False, None
    except requests.exceptions.ConnectionError as e:
        log(f"  ❌ Connection error: {e}", "ERROR")
        return False, None
    except Exception as e:
        log(f"  ❌ Unexpected error: {e}", "ERROR")
        return False, None


def diagnose_api():
    """Run comprehensive API diagnostics."""
    log("=== Running API Diagnostics ===", "INFO")

    # Test 1: Health endpoint (no auth required)
    log("\n1️⃣ Testing health endpoint (no auth)...", "INFO")
    test_endpoint(HEALTH_ENDPOINT, description="Health")

    # Test 2: Main endpoint without auth
    log("\n2️⃣ Testing main endpoint WITHOUT API key...", "INFO")
    test_endpoint(API_ENDPOINT, description="Main endpoint (no auth)")

    # Test 3: Main endpoint with auth
    log("\n3️⃣ Testing main endpoint WITH API key...", "INFO")
    headers = {"X-API-Key": API_KEY}
    success, response = test_endpoint(API_ENDPOINT, headers=headers, description="Main endpoint (with auth)")

    if success:
        log("✅ Main endpoint works with API key!", "SUCCESS")
        return True, response

    # Test 4: Try alternate endpoints
    log("\n4️⃣ Trying alternate endpoints...", "INFO")
    for alt_url in ALTERNATE_ENDPOINTS:
        log(f"\nTrying: {alt_url}", "INFO")

        # Try without auth
        success, response = test_endpoint(alt_url, description="Alternate (no auth)")
        if success:
            return True, response

        # Try with auth
        success, response = test_endpoint(alt_url, headers=headers, description="Alternate (with auth)")
        if success:
            return True, response

    log("\n❌ No working endpoints found!", "ERROR")
    return False, None


def start_server():
    """Start the backend server."""
    log("Starting backend server...", "INFO")

    try:
        # Set environment variable for API key
        env = os.environ.copy()
        env["API_KEY"] = API_KEY

        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "web_service.backend.main:app",
             "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        log(f"Backend process started (PID: {proc.pid})", "SUCCESS")
        log(f"Waiting {INITIAL_WAIT} seconds for initialization...", "INFO")
        time.sleep(INITIAL_WAIT)

        return proc
    except Exception as e:
        log(f"Failed to start server: {e}", "ERROR")
        return None


def wait_for_health(timeout_seconds=HEALTH_CHECK_TIMEOUT):
    """Wait for backend to become healthy."""
    log(f"Checking backend health (timeout: {timeout_seconds}s)...", "INFO")

    start_time = time.time()
    attempt = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            log(f"Health check timeout after {elapsed:.0f} seconds", "ERROR")
            return False

        attempt += 1
        try:
            response = requests.get(HEALTH_ENDPOINT, timeout=5)
            if response.status_code == 200:
                log(f"Backend is healthy! (attempt {attempt}, {elapsed:.0f}s)", "SUCCESS")
                return True
        except requests.RequestException:
            pass

        if attempt % 3 == 0:  # Log every 3rd attempt
            log(f"Health check attempt {attempt} failed, retrying...", "WARNING")
        time.sleep(HEALTH_CHECK_INTERVAL)


def query_races():
    """Query for race data with fallback logic."""
    log("Querying API for race data...", "INFO")

    # First, diagnose the API
    success, response = diagnose_api()

    if not success:
        log("Could not find a working endpoint", "ERROR")
        log("💡 Check your backend code for:", "INFO")
        log("   1. Does /api/races/qualified/tiny_field_trifecta exist?", "INFO")
        log("   2. Does it require authentication?", "INFO")
        log("   3. What API key format does it expect?", "INFO")
        log("   4. Are there CORS or middleware issues?", "INFO")
        return None

    # Parse the successful response
    try:
        data = response.json()

        # Handle different response formats
        if isinstance(data, dict):
            races = data.get("races", []) or data.get("data", []) or []
        elif isinstance(data, list):
            races = data
        else:
            races = []

        log(f"Successfully retrieved {len(races)} races", "SUCCESS")

        # Ensure consistent format
        return {"races": races, "timestamp": datetime.now().isoformat()}

    except json.JSONDecodeError:
        log("Response was not valid JSON", "ERROR")
        return None


def generate_report(race_data):
    """Generate HTML report."""
    log("Generating HTML report...", "INFO")

    try:
        if not os.path.exists(TEMPLATE_PATH):
            log(f"Template not found at {TEMPLATE_PATH}", "WARNING")
            log("Creating simple fallback HTML...", "INFO")

            # Create a simple HTML report
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Fortuna Race Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                    .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
                    h1 {{ color: #333; }}
                    pre {{ background: #f0f0f0; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🐴 Fortuna Race Report</h1>
                    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <h2>Race Data ({len(race_data.get('races', []))} races)</h2>
                    <pre>{json.dumps(race_data, indent=2)}</pre>
                </div>
            </body>
            </html>
            """

            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(html)

        else:
            # Use template
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                template = f.read()

            report_html = template.replace("__RACE_DATA_PLACEHOLDER__", json.dumps(race_data))

            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(report_html)

        log(f"Report saved to {OUTPUT_PATH}", "SUCCESS")
        return True

    except Exception as e:
        log(f"Failed to generate report: {e}", "ERROR")
        return False


def save_json_data(race_data):
    """Save JSON data."""
    try:
        with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(race_data, f, indent=2)
        log(f"JSON data saved to {JSON_OUTPUT_PATH}", "SUCCESS")
        return True
    except Exception as e:
        log(f"Failed to save JSON: {e}", "ERROR")
        return False


def main():
    """Main entry point."""
    log("=== Fortuna Enhanced Race Report Generator ===", "INFO")
    log(f"API Key (first 10 chars): {API_KEY[:10]}...", "DEBUG")

    server_process = None

    try:
        # Start server
        server_process = start_server()
        if not server_process:
            return 1

        # Wait for health
        if not wait_for_health(HEALTH_CHECK_TIMEOUT):
            log("Backend did not become healthy", "ERROR")
            return 1

        # Query races (with diagnostics)
        race_data = query_races()
        if race_data is None:
            log("Failed to fetch race data", "ERROR")
            return 1

        # Save outputs
        save_json_data(race_data)

        if not generate_report(race_data):
            log("Failed to generate report", "ERROR")
            return 1

        log("=== SUCCESS ===", "SUCCESS")
        return 0

    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        if server_process:
            log("Stopping backend server...", "INFO")
            try:
                server_process.terminate()
                server_process.wait(timeout=5)
                log("Backend stopped", "SUCCESS")
            except subprocess.TimeoutExpired:
                log("Forcing backend termination...", "WARNING")
                server_process.kill()
                server_process.wait()
            except Exception as e:
                log(f"Error during cleanup: {e}", "WARNING")


if __name__ == "__main__":
    sys.exit(main())
