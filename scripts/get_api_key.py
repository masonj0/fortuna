# scripts/get_api_key.py
import os
import sys

# This is a workaround to ensure the script can find the python_service module,
# especially when run from the packaged Electron app.
# It assumes this script is in `resources/app/scripts` and the service is in `resources/app/python_service`.
try:
    # Get the directory of the current script.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to the `app` directory and add `python_service` to the path.
    project_root = os.path.dirname(script_dir)
    sys.path.append(project_root)
    from python_service.credentials_manager import SecureCredentialsManager
except ImportError as e:
    # If the import fails, write the error to stderr and exit.
    # This helps in debugging path issues in the production environment.
    print(f"Error: Failed to import SecureCredentialsManager. Details: {e}", file=sys.stderr)
    sys.exit(1)


def retrieve_and_print_key():
    """
    Retrieves the API key using the SecureCredentialsManager and prints it to stdout.
    If the key is not found, it prints an empty string.
    If an error occurs, it prints the error to stderr.
    """
    try:
        api_key = SecureCredentialsManager.get_api_key()
        if api_key:
            print(api_key, end="")  # Print the key directly to stdout
        else:
            print("", end="")  # Print empty string if no key is found
    except Exception as e:
        print(f"An error occurred while retrieving the API key: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    retrieve_and_print_key()
