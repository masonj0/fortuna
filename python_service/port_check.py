import socket
import sys


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """
    Checks if a local port is already in use.

    Args:
        port: The port number to check.
        host: The host to check (defaults to localhost).

    Returns:
        True if the port is in use, False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def check_port_and_exit_if_in_use(port: int, host: str = "127.0.0.1"):
    """
    Checks the specified port and exits the application with a user-friendly
    message if it's already in use.
    """
    # Note: A simple s.connect_ex((host, port)) == 0 is not reliable, as it can
    # intermittently fail depending on socket states. A full bind attempt is
    # the most robust way to check for port availability.
    if is_port_in_use(port, host):
        print(f"--- FATAL ERROR ---")
        print(f"Port {port} on host {host} is already in use by another application.")
        print(f"Please close the other application or configure Fortuna Faucet to use a different port.")
        print(f"-------------------")
        # Use sys.exit to ensure a clean exit, especially important for PyInstaller executables.
        sys.exit(1)
