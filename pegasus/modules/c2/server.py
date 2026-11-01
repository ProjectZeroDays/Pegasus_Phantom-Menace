"""Standalone C2 listener on an ephemeral port."""
import threading

from flask import Flask, jsonify
from werkzeug.serving import ThreadedWSGIServer, make_server

from . import beacon_routes

_server: ThreadedWSGIServer | None = None


def start(port: int = 0) -> int:
    global _server
    app = Flask("c2")
    ok = lambda data, code=200: (jsonify({"ok": True, "data": data}), code)  # noqa: E731
    fail = lambda err, code=400: (jsonify({"ok": False, "error": err}), code)  # noqa: E731
    beacon_routes.register(app, ok, fail)
    _server = make_server("0.0.0.0", port, app, threaded=True)
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    return _server.server_port


def stop() -> None:
    global _server
    if _server:
        _server.shutdown()
        _server = None
