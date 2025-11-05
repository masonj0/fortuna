# check_port.py
import socket
import time


def check_server_status(host, port):
    """Checks if the server is accessible."""
    time.sleep(5)  # Give server time to start
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            print("SERVER CHECK: SUCCESS! Server is running and accessible.")
            return True
        except ConnectionRefusedError:
            print("SERVER CHECK: FAILED! Server is not accessible.")
            return False


if __name__ == "__main__":
    check_server_status("127.0.0.1", 8000)
