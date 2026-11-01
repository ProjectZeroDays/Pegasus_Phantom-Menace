"""First-run setup."""
from flask import request

from .ai import catalog, local_models, providers
from .ai.router import generate as ai_generate
import asyncio


def register(app, ok, fail):
    @app.get("/api/setup/state")
    def setup_state():
        data = providers.load()
        return ok({"needsSetup": providers.needs_setup(),
                   "providers": [{"id": k, "label": v["label"], "kind": v["kind"]}
                                 for k, v in providers.REGISTRY.items()],
                   "configured": providers.configured(),
                   "default": data.get("default"),
                   "fallback": data.get("fallback"),
                   "platform": catalog.os_key()})

    @app.post("/api/setup/providers")
    def setup_providers():
        body = request.get_json(silent=True) or {}
        data = providers.load()
        for name, key in (body.get("keys") or {}).items():
            if name in providers.REGISTRY and key:
                data.setdefault("keys", {})[name] = key.strip()
        for field in ("default", "fallback"):
            if body.get(field):
                data[field] = body[field]
        if not (data.get("default") or data.get("fallback")):
            data["default"] = next(iter(data.get("keys", {})), None)
        providers.save(data)
        return ok({"configured": providers.configured(), "default": data.get("default")})

    @app.post("/api/setup/skip")
    def setup_skip():
        data = providers.load()
        data["default"] = "local"
        providers.save(data)
        return ok({"default": "local"})

    @app.post("/api/setup/test")
    def setup_test():
        try:
            asyncio.run(ai_generate(catalog.Role.PLANNER, "ping"))
            return ok({"ok": True})
        except Exception as exc:
            return fail(str(exc), 502)
