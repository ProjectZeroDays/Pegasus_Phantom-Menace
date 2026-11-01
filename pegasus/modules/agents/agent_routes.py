"""Agent routes."""
from flask import request

from . import bridge


def register(app, ok, fail):
    @app.get("/api/agents/available")
    def agents_available():
        return ok({"available": bridge.available()})

    @app.get("/api/agents/config")
    def agents_config():
        return ok({"config": bridge.load(), "available": bridge.available()})

    @app.post("/api/agents/config")
    def agents_set_config():
        body = request.get_json(silent=True) or {}
        cfg = bridge.load()
        for field in ("agent", "provider", "model", "skills"):
            if field in body:
                cfg[field] = body[field]
        if cfg.get("agent") and not bridge.available().get(cfg["agent"]):
            return fail(f"{cfg['agent']} is not on PATH")
        bridge.save(cfg)
        return ok({"config": cfg})

    @app.post("/api/agents/dispatch")
    def agents_dispatch():
        body = request.get_json(silent=True) or {}
        if not body.get("prompt"):
            return fail("prompt required")
        try:
            return ok(bridge.dispatch(body["prompt"], body.get("cwd", ".")))
        except Exception as exc:
            return fail(str(exc), 503)
