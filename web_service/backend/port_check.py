import socket
import sys

def check_port_and_exit_if_in_use(port: int, host: str):
    """Checks if a port is in use at the given host and exits if it is."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            print(f"❌ FATAL: Port {port} is already in use. Please close the other application or specify a different port.")
            sys.exit(1)
