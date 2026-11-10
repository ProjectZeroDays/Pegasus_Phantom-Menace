"""KYC onboarding links and status.

The console opens the operator's chosen compliance provider in the embedded
webview and records which provider and stage the engagement is at.  It does
not attempt to complete, bypass or automate identity verification.
"""
from __future__ import annotations

import json
import pathlib
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.auth import operator

STATE_FILE = pathlib.Path.home() / ".pegasus" / "kyc.json"

PROVIDERS = [
    {"id": "persona", "name": "Persona", "url": "https://withpersona.com/",
     "stage": "identity document + selfie"},
    {"id": "sumsub", "name": "Sumsub", "url": "https://sumsub.com/",
     "stage": "document, selfie and address"},
    {"id": "onfido", "name": "Onfido", "url": "https://onfido.com/",
     "stage": "document and biometric capture"},
    {"id": "jumio", "name": "Jumio", "url": "https://jumio.com/",
     "stage": "document and face capture"},
]


def _read() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register(app, ok, fail):
    @app.get("/api/kyc/providers")
    @operator.require("viewer")
    def kyc_providers():
        state = _read()
        entries = []
        for provider in PROVIDERS:
            entry = dict(provider)
            entry["status"] = state.get(provider["id"], {}).get("status", "not started")
            entries.append(entry)
        return ok({"providers": entries})

    @app.get("/api/kyc/status")
    @operator.require("viewer")
    def kyc_status():
        op = operator.current()
        state = _read()
        entry = state.get(op["user"], {})
        return ok({"kyc": entry, "providers": PROVIDERS})

    @app.post("/api/kyc/start")
    @operator.require("operator")
    def kyc_start():
        body = request.get_json(silent=True) or {}
        provider = body.get("provider")
        if provider not in {p["id"] for p in PROVIDERS}:
            return fail("unknown provider", 400)
        op = operator.current()
        state = _read()
        entry = {"provider": provider, "status": "in progress",
                 "started": time.time(), "operator": op["user"],
                 "webview_url": next(p["url"] for p in PROVIDERS
                                     if p["id"] == provider)}
        state[op["user"]] = entry
        state.setdefault(provider, {})["status"] = "in progress"
        _write(state)
        return ok({"kyc": entry})

    @app.post("/api/kyc/status")
    @operator.require("operator")
    def kyc_set_status():
        body = request.get_json(silent=True) or {}
        status = body.get("status")
        allowed = {"not started", "in progress", "submitted", "approved",
                   "rejected", "needs review"}
        if status not in allowed:
            return fail("unsupported status", 400)
        op = operator.current()
        state = _read()
        entry = state.get(op["user"], {})
        entry["status"] = status
        entry["updated"] = time.time()
        state[op["user"]] = entry
        _write(state)
        return ok({"kyc": entry})
