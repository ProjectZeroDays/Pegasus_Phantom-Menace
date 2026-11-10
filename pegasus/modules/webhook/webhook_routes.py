"""Webhook routes - in-memory registry with HMAC-SHA256 signed delivery."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.request
import uuid
from pathlib import Path

from flask import request

_REGISTRY: dict[str, dict] = {}
_EVENTS_PATH = Path.home() / ".pegasus" / "webhook_events.jsonl"
_MAX_EVENTS = 200


def _events() -> list[dict]:
    if not _EVENTS_PATH.exists():
        return []
    rows = []
    for line in _EVENTS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-_MAX_EVENTS:]


def _log(entry: dict) -> None:
    _EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _EVENTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def register(app, ok, fail):
    @app.get("/api/webhooks")
    def webhooks_list():
        return ok({"webhooks": list(_REGISTRY.values())})

    @app.post("/api/webhooks")
    def webhooks_create():
        data = request.get_json(silent=True) or {}
        url = data.get("url")
        events = data.get("events") or ["*"]
        if not url:
            return fail("url required")
        wh_id = uuid.uuid4().hex[:12]
        hook = {
            "id": wh_id,
            "url": url,
            "events": events if isinstance(events, list) else [events],
            "secret": data.get("secret") or "",
            "active": True,
            "created_at": time.time(),
            "max_retries": int(data.get("max_retries", 3)),
            "timeout": int(data.get("timeout", 10)),
        }
        _REGISTRY[wh_id] = hook
        return ok({"webhook": hook})

    @app.delete("/api/webhooks/<wh_id>")
    def webhooks_delete(wh_id):
        existed = _REGISTRY.pop(wh_id, None)
        return ok({"deleted": bool(existed)})

    @app.get("/api/webhooks/events")
    def webhooks_events():
        return ok({"events": _events()})

    @app.post("/api/webhooks/test")
    def webhooks_test():
        data = request.get_json(silent=True) or {}
        entry = _REGISTRY.get(data.get("id")) if data.get("id") else None
        target = (entry or {}).get("url") or data.get("url")
        if not target:
            return fail("id or url required")
        secret = (entry or {}).get("secret") or data.get("secret") or ""
        body = json.dumps({
            "event": "pegasus.test",
            "ts": time.time(),
            "payload": {"message": "operator test fire from Pegasus Phantom Menace"},
        }).encode()
        headers = {"Content-Type": "application/json", "User-Agent": "Pegasus-PhantomMenace/2.1"}
        if secret:
            headers["X-Pegasus-Signature"] = _sign(secret, body)
        result = {"target": target, "event": "pegasus.test", "ts": time.time()}
        try:
            req = urllib.request.Request(target, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=int((entry or {}).get("timeout", 10))) as resp:
                result["status"] = resp.status
                result["delivered"] = 200 <= resp.status < 300
        except Exception as exc:
            result["status"] = 0
            result["delivered"] = False
            result["error"] = str(exc)
        _log(result)
        return ok({"result": result, "signed": bool(secret)})
