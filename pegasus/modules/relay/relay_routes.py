"""Relay routes."""
from flask import request

from . import tunnel

_ACTIVE: dict[str, tunnel.Tunnel] = {}


def register(app, ok, fail):
    @app.post("/api/relay/start")
    def relay_start():
        port = (request.get_json(silent=True) or {}).get("port", 5001)
        t = tunnel.Tunnel()
        url = t.start(port)
        if not url:
            return fail("no tunnel binary on PATH", 503)
        _ACTIVE["current"] = t
        return ok({"url": url})

    @app.delete("/api/relay")
    def relay_stop():
        t = _ACTIVE.pop("current", None)
        if t:
            t.stop()
        return ok({"stopped": bool(t)})
