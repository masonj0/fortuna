import json
import os
import sys
import time
import subprocess
import requests

API_ENDPOINT = "http://127.0.0.1:8000/api/races/qualified/tiny_field_trifecta"
TEMPLATE_PATH = "scripts/templates/race_report_template.html"
OUTPUT_PATH = "race-report.html"
API_KEY = os.environ.get("API_KEY", "a_secure_test_api_key_that_is_long_enough")

def start_server():
    """Starts the backend server in a background process."""
    print("--- Starting backend server ---")
    # Use sys.executable to ensure we're using the same python
    # In a GH Action, the python used for the script might not be the same one on the path
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_service.backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Give the server a moment to start up
    time.sleep(10)
    print("--- Backend server started ---")
    return proc

def query_races():
    """Queries the API for qualified races."""
    print(f"--- Querying API endpoint: {API_ENDPOINT} ---")
    headers = {"X-API-Key": API_KEY}
    response = requests.get(API_ENDPOINT, headers=headers)
    response.raise_for_status()
    print("--- API query successful ---")
    return response.json()

def generate_report(race_data):
    """Injects race data into the HTML template."""
    print("--- Generating HTML report ---")
    with open(TEMPLATE_PATH, "r") as f:
        template = f.read()

    # The template expects a simple replacement of a placeholder
    # with the JSON data.
    report_html = template.replace("__RACE_DATA_PLACEHOLDER__", json.dumps(race_data))

    with open(OUTPUT_PATH, "w") as f:
        f.write(report_html)
    print(f"--- Report saved to {OUTPUT_PATH} ---")

def main():
    server_process = None
    try:
        server_process = start_server()

        # Health check before querying
        for _ in range(5):
             try:
                 health_response = requests.get("http://127.0.0.1:8000/api/health")
                 if health_response.status_code == 200:
                     print("--- Health check passed ---")
                     break
             except requests.ConnectionError:
                 print("--- Waiting for server to be healthy... ---")
                 time.sleep(5)
        else:
            raise Exception("Server did not become healthy in time.")

        race_data = query_races()
        generate_report(race_data)

    except Exception as e:
        print(f"An error occurred: {e}")
        if server_process:
            print("--- Server logs ---")
            stdout, stderr = server_process.communicate()
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
        sys.exit(1)
    finally:
        if server_process:
            server_process.terminate()
            server_process.wait()
            print("--- Backend server stopped ---")

if __name__ == "__main__":
    main()
