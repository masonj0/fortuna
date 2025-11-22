import socket
import sys


def is_port_available(port=8000):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result != 0
    except Exception:
        return False


if __name__ == "__main__":
    if not is_port_available(8000):
        print("ERROR: Port 8000 already in use. Kill existing process or use different port.")
        sys.exit(1)
    print("Port 8000 available ✓")
