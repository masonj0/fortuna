#!/usr/bin/env python
"""
Fixed Fortuna Race Report Query Script

This script:
1. Starts the backend server
2. Waits for health check with proper timeout
3. Queries filtered races
4. Generates HTML report
5. Cleans up gracefully

CRITICAL: This version has proper error handling and will NOT hang.
"""

import json
import os
import sys
import time
import subprocess
import requests
from datetime import datetime

# Configuration
API_ENDPOINT = "http://127.0.0.1:8000/api/races/qualified/tiny_field_trifecta"
HEALTH_ENDPOINT = "http://127.0.0.1:8000/api/health"
TEMPLATE_PATH = "scripts/templates/race_report_template.html"
OUTPUT_PATH = "race-report.html"
JSON_OUTPUT_PATH = "qualified_races.json"
API_KEY = os.environ.get("API_KEY")

# Timeouts (in seconds)
INITIAL_WAIT = 5  # Give server 5 seconds to start
HEALTH_CHECK_TIMEOUT = 60  # Total time to wait for health
HEALTH_CHECK_INTERVAL = 5  # Check every 5 seconds
API_QUERY_TIMEOUT = 30  # API query timeout


def log(message, level="INFO"):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
    print(f"[{timestamp}] {emoji.get(level, '•')} {message}")


def start_server():
    """Starts the backend server in a background process."""
    log("Starting backend server...", "INFO")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "web_service.backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log(f"Backend process started (PID: {proc.pid})", "SUCCESS")

        # Give server initial time to start
        log(f"Waiting {INITIAL_WAIT} seconds for server initialization...", "INFO")
        time.sleep(INITIAL_WAIT)

        return proc
    except Exception as e:
        log(f"Failed to start server: {e}", "ERROR")
        return None


def wait_for_health(timeout_seconds=HEALTH_CHECK_TIMEOUT):
    """
    Poll health endpoint until backend responds or timeout.

    Args:
        timeout_seconds: Maximum time to wait in seconds

    Returns:
        True if healthy, False if timeout
    """
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
            pass  # Will retry

        log(f"Health check attempt {attempt} failed, retrying in {HEALTH_CHECK_INTERVAL}s...", "WARNING")
        time.sleep(HEALTH_CHECK_INTERVAL)


def query_races(timeout_seconds=API_QUERY_TIMEOUT):
    """
    Queries the API for qualified races.

    Args:
        timeout_seconds: Request timeout in seconds

    Returns:
        Race data dict or None if failed
    """
    log(f"Querying API: {API_ENDPOINT}", "INFO")

    # Check for API Key
    if not API_KEY:
        log("API_KEY environment variable is not set. Cannot authenticate.", "ERROR")
        return None

    try:
        headers = {"X-API-Key": api_key}
        response = requests.get(API_ENDPOINT, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()

        data = response.json()
        race_count = len(data.get("races", []))
        log(f"Successfully retrieved {race_count} races", "SUCCESS")
        return data

    except requests.exceptions.Timeout:
        log(f"API request timed out after {timeout_seconds} seconds", "ERROR")
        return None
    except requests.exceptions.ConnectionError as e:
        log(f"Connection error: {e}", "ERROR")
        return None
    except requests.exceptions.HTTPError as e:
        log(f"HTTP error: {response.status_code}", "ERROR")
        return None
    except json.JSONDecodeError:
        log("API response was not valid JSON", "ERROR")
        return None
    except Exception as e:
        log(f"Unexpected error during query: {e}", "ERROR")
        return None


def generate_report(race_data):
    """
    Injects race data into the HTML template.

    Args:
        race_data: Dictionary containing race information

    Returns:
        True if successful, False otherwise
    """
    log(f"Generating HTML report...", "INFO")

    try:
        # Check if template exists
        if not os.path.exists(TEMPLATE_PATH):
            log(f"Template not found at {TEMPLATE_PATH}", "ERROR")
            log("Creating minimal fallback HTML...", "WARNING")
            fallback_html = f"<pre>{json.dumps(race_data, indent=2)}</pre>"
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(fallback_html)
            return True

        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = f.read()

        # Replace placeholder with race data
        report_html = template.replace("__RACE_DATA_PLACEHOLDER__", json.dumps(race_data))

        # Write report
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(report_html)

        log(f"Report saved to {OUTPUT_PATH}", "SUCCESS")
        return True

    except Exception as e:
        log(f"Failed to generate report: {e}", "ERROR")
        return False


def save_json_data(race_data):
    """
    Save race data to JSON file.

    Args:
        race_data: Dictionary containing race information

    Returns:
        True if successful, False otherwise
    """
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
    log("=== Fortuna Race Report Generator ===", "INFO")

    server_process = None

    try:
        # Step 1: Start server
        server_process = start_server()
        if not server_process:
            log("Failed to start backend server", "ERROR")
            return 1

        # Step 2: Wait for health
        if not wait_for_health(HEALTH_CHECK_TIMEOUT):
            log("Backend did not become healthy in time", "ERROR")
            return 1

        # Step 3: Query races
        race_data = query_races(API_QUERY_TIMEOUT)
        if race_data is None:
            log("Failed to fetch race data", "ERROR")
            return 1

        # Step 4: Save JSON
        save_json_data(race_data)

        # Step 5: Generate report
        if not generate_report(race_data):
            log("Failed to generate report", "ERROR")
            return 1

        log("=== SUCCESS ===", "SUCCESS")
        return 0

    except Exception as e:
        log(f"Unexpected error in main: {e}", "ERROR")
        return 1

    finally:
        # Step 6: Cleanup
        if server_process:
            log("Stopping backend server...", "INFO")
            try:
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                    log("Backend stopped cleanly", "SUCCESS")
                except subprocess.TimeoutExpired:
                    log("Backend did not stop, forcing termination...", "WARNING")
                    server_process.kill()
                    server_process.wait()
            except Exception as e:
                log(f"Error during cleanup: {e}", "WARNING")


if __name__ == "__main__":
    sys.exit(main())
