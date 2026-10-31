#!/usr/bin/env python3
"""Setup wizard routes."""
from flask import request, jsonify
from pegasus.modules.ai import providers, local_models

def register(app, ok, fail):
    @app.get("/api/setup/state")
    def setup_state():
        return ok({
            "needsSetup": providers.needs_setup(),
            "providers": [{"id": k, **v} for k, v in providers.REGISTRY.items()],
            "configured": providers.configured(),
            "default": providers.load().get("default"),
            "fallback": providers.load().get("fallback"),
            "localModel": local_models.installed_default(),
            "platform": local_models.platform_tier(),
        })

    @app.post("/api/setup/providers")
    def setup_providers():
        body = request.get_json(silent=True) or {}
        data = providers.load()
        for name, key in (body.get("keys") or {}).items():
            if name in providers.REGISTRY and key:
                data.setdefault("keys", {})[name] = key
        if body.get("default"):
            data["default"] = body["default"]
        if body.get("fallback"):
            data["fallback"] = body["fallback"]
        providers.save(data)
        return ok({"configured": providers.configured(), "default": data.get("default")})

    @app.post("/api/setup/skip")
    def setup_skip():
        data = providers.load()
        data["default"] = "local"
        providers.save(data)
        return ok({"default": "local"})
