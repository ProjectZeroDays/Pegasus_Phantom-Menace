"""Single source of truth for bind address."""
import os


def port() -> int:
    return int(os.environ.get("PEGASUS_PORT", "5001"))


def host() -> str:
    return os.environ.get("PEGASUS_HOST", "127.0.0.1")


def base_url() -> str:
    h = "127.0.0.1" if host() in ("0.0.0.0", "::") else host()
    return f"http://{h}:{port()}"


def lan_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def public_url() -> str:
    explicit = os.environ.get("PEGASUS_PUBLIC_URL")
    if explicit:
        return explicit.rstrip("/")
    return f"http://{lan_ip()}:{port()}"
