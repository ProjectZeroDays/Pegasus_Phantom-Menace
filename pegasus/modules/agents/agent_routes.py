#!/usr/bin/env python3
from flask import request
from pegasus.ui.web.backend.app import ok, fail
import json, pathlib, shutil, subprocess, os

CONFIG = pathlib.Path.home() / ".pegasus" / "agents.json"
AGENTS = {"opencode":"opencode","mimicode":"mimicode"}

def register(app, ok_fn, fail_fn):
    @app.get("/api/agents/config")
    def agent_config():
        if CONFIG.exists():
            try: return ok(json.loads(CONFIG.read_text()))
            except: pass
        return ok({"agent": None, "provider": None, "model": None, "skills": ".openfable-skills"})

    @app.post("/api/agents/config")
    def agent_config_save():
        body = request.get_json(silent=True) or {}
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(body, indent=2))
        return ok({"saved": True})

    @app.get("/api/agents/available")
    def agent_available():
        return ok({k: bool(shutil.which(v)) for k, v in AGENTS.items()})
