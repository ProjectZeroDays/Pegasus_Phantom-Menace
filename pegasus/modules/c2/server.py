"""Standalone C2 listener.

The listener follows the console's own posture: loopback unless the operator
opts into exposure. ``start()`` takes an explicit host so a caller can bind
deliberately, and ``PEGASUS_C2_TLS`` turns on TLS so ``wss://`` clients can
complete a handshake against this plain-HTTP-by-default server.
"""
import os
import threading

from flask import Flask, jsonify
from werkzeug.serving import ThreadedWSGIServer, make_server

from . import beacon_routes

_server: ThreadedWSGIServer | None = None
_BOUND_HOST: str | None = None


def c2_host() -> str:
    """Loopback unless the operator opts into network exposure."""
    return os.getenv("PEGASUS_C2_HOST", "127.0.0.1").strip() or "127.0.0.1"


def _ssl_context():
    """TLS for wss:// clients.

    unset/0 -> plain HTTP, 1/adhoc -> self-signed cert minted by werkzeug,
    any other value -> an explicit certfile, or ``certfile:keyfile``.
    """
    mode = os.getenv("PEGASUS_C2_TLS", "0").strip().lower()
    if mode in ("", "0", "false", "no", "off"):
        return None
    if mode in ("1", "true", "yes", "on", "adhoc"):
        return "adhoc"
    return mode


def start(port: int = 0, host: str | None = None) -> int:
    global _server, _BOUND_HOST
    host = host or c2_host()
    app = Flask("c2")
    ok = lambda data, code=200: (jsonify({"ok": True, "data": data}), code)  # noqa: E731
    fail = lambda err, code=400: (jsonify({"ok": False, "error": err}), code)  # noqa: E731
    beacon_routes.register(app, ok, fail)
    _server = make_server(host, port, app, threaded=True,
                          ssl_context=_ssl_context())
    _BOUND_HOST = host
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    return _server.server_port


def bound_host() -> str | None:
    return _BOUND_HOST


def tls_enabled() -> bool:
    return _ssl_context() is not None


def stop() -> None:
    global _server, _BOUND_HOST
    if _server:
        _server.shutdown()
        _server = None
        _BOUND_HOST = None
