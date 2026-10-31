#!/usr/bin/env python3
"""AI model routes for the web GUI."""
from flask import request
from pegasus.modules.ai import local_models
from pegasus.ui.web.backend.app import ok, fail

def register(app, ok_fn, fail_fn):
    @app.get("/api/models/recommended")
    def models_recommended():
        return ok({"models": local_models.recommended(), "platform": local_models.platform_tier()})

    @app.get("/api/models/installed")
    def models_installed():
        return ok({"installed": local_models.installed(), "default": local_models.installed_default()})

    @app.post("/api/models/download")
    def models_download():
        body = request.get_json(silent=True) or {}
        return ok(local_models.download(body.get("model","claude-sonnet-4-6"), body.get("filename","model.gguf")))

    @app.post("/api/models/select")
    def models_select():
        body = request.get_json(silent=True) or {}
        # Persist selection to providers.json (stub)
        from pegasus.modules.ai.providers import load, save
        data = load(); data["default"] = "local"; data.setdefault("keys",{}); data["localModel"] = body.get("model")
        save(data)
        return ok({"selected": body.get("model"), "local_path": str(local_models.MODELS / body.get("filename","model.gguf"))})

    @app.post("/api/models/serve")
    def models_serve():
        body = request.get_json(silent=True) or {}
        import pathlib
        p = pathlib.Path(body.get("filename"))
        return ok({"url": local_models.serve(local_models.MODELS / p.name, body.get("port", 8081))})
