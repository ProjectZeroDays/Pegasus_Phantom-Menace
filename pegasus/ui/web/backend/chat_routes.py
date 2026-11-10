"""Chat dock routes: Venice.ai and the local coding agent.

Venice.ai is proxied server side so the API key never reaches the browser.
When no Venice key is configured the endpoint reports the missing credential
instead of pretending to answer.  The local agent route uses the provider
configuration that the Settings panel writes into ``.env``.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.auth import operator

VENICE_URL = "https://api.venice.ai/api/v1/chat/completions"
DEFAULT_MODEL = "venice-ai/gpt-4.1"


def _venice_key() -> str:
    for name in ("PEGASUS__AI__API_KEY", "VENICE_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    env_path = pathlib.Path(__file__).resolve().parents[4] / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VENICE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def register(app, ok, fail):
    @app.get("/api/chat/providers")
    @operator.require("viewer")
    def chat_providers():
        return ok({
            "providers": [
                {"id": "venice", "name": "Venice.ai", "key_present": bool(_venice_key()),
                 "default_model": DEFAULT_MODEL},
                {"id": "agent", "name": "Local coding agent", "key_present": False,
                 "default_model": ""},
            ]
        })

    @app.post("/api/chat/venice")
    @operator.require("operator")
    def chat_venice():
        body = request.get_json(silent=True) or {}
        messages = body.get("messages") or []
        if not messages:
            return fail("messages required")
        key = _venice_key()
        if not key:
            return fail("Venice.ai is not configured - set VENICE_API_KEY", 409)
        payload = {
            "model": body.get("model") or DEFAULT_MODEL,
            "messages": messages,
            "stream": False,
        }
        try:
            from urllib import request as urlrequest
            req = urlrequest.Request(
                VENICE_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"},
            )
            with urlrequest.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001
            return fail(f"Venice.ai request failed: {exc}", 502)
        reply = ""
        choices = data.get("choices") or []
        if choices:
            reply = (choices[0].get("message") or {}).get("content") or ""
        return ok({"reply": reply, "model": payload["model"],
                   "usage": data.get("usage", {})})

    @app.post("/api/chat/agent")
    @operator.require("operator")
    def chat_agent():
        """Route the prompt through the configured coding agent provider."""
        body = request.get_json(silent=True) or {}
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return fail("prompt required")
        try:
            from pegasus.modules.ai import providers
            provider = providers.get_provider(body.get("provider") or "")
        except Exception as exc:  # noqa: BLE001
            return fail(f"agent unavailable: {exc}", 503)
        if provider is None:
            return fail("no agent provider configured", 409)
        try:
            result = provider.complete([{"role": "user", "content": prompt}])
        except Exception as exc:  # noqa: BLE001
            return fail(f"agent failed: {exc}", 502)
        return ok({"reply": result if isinstance(result, str) else str(result),
                   "provider": body.get("provider") or ""})

    @app.get("/api/chat/history")
    @operator.require("viewer")
    def chat_history():
        path = pathlib.Path.home() / ".pegasus" / "chat_history.json"
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            history = []
        return ok({"history": history[-50:]})
