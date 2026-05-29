import socket


def check_is_reachable(hostname: str) -> bool:
    try:
        host: str = socket.gethostbyname(hostname)
    except Exception:
        return False

    try:
        sock: socket.socket = socket.create_connection((host, 80), 2)
        sock.close()
    except Exception:
        return False

    return True
