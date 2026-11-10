"""Social engineering routes - authorized simulated-phishing and awareness program mgmt."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from flask import request

_CAMPAIGNS = Path.home() / ".pegasus" / "se_campaigns.jsonl"
_RESULTS = Path.home() / ".pegasus" / "se_results.jsonl"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


_TEMPLATES = [
    {"id": "t-mfa-reset", "name": "MFA reset notice", "channel": "email", "difficulty": "easy"},
    {"id": "t-payroll-update", "name": "Payroll direct-deposit update", "channel": "email", "difficulty": "medium"},
    {"id": "t-shared-doc", "name": "Shared document notification", "channel": "email", "difficulty": "medium"},
    {"id": "t-courier", "name": "Courier / delivery SMS", "channel": "sms", "difficulty": "easy"},
    {"id": "t-vendor-invoice", "name": "Vendor invoice attachment", "channel": "email", "difficulty": "hard"},
    {"id": "t-hr-policy", "name": "HR policy acknowledgment", "channel": "email", "difficulty": "easy"},
    {"id": "t-voicemail", "name": "Voicemail transcript lure", "channel": "email", "difficulty": "medium"},
    {"id": "t-usb-drop", "name": "USB drop awareness exercise", "channel": "physical", "difficulty": "hard"},
]

_AWARENESS = [
    {"id": "mod-phishing", "name": "Phishing recognition", "minutes": 15, "audience": "all"},
    {"id": "mod-pretexting", "name": "Pretexting and impersonation", "minutes": 20, "audience": "frontline"},
    {"id": "mod-vishing", "name": "Vishing / phone social engineering", "minutes": 10, "audience": "helpdesk"},
    {"id": "mod-mfa", "name": "MFA pressure-attack resilience", "minutes": 10, "audience": "all"},
    {"id": "mod-reporting", "name": "Reporting suspicious activity", "minutes": 5, "audience": "all"},
]


def register(app, ok, fail):
    @app.get("/api/se/status")
    def se_status():
        campaigns = _load(_CAMPAIGNS)
        results = _load(_RESULTS)
        sent = sum(r.get("sent", 0) for r in results)
        clicked = sum(r.get("clicked", 0) for r in results)
        return ok({
            "templates": len(_TEMPLATES),
            "awareness_modules": len(_AWARENESS),
            "campaigns": len(campaigns),
            "messages_sent": sent,
            "click_rate": round(clicked / sent, 4) if sent else 0.0,
            "mode": "authorized-awareness-training (simulated phishing, opt-in targets)",
        })

    @app.get("/api/se/templates")
    def se_templates():
        return ok({"templates": _TEMPLATES})

    @app.get("/api/se/awareness")
    def se_awareness():
        return ok({"modules": _AWARENESS})

    @app.get("/api/se/campaigns")
    def se_campaigns():
        return ok({"campaigns": _load(_CAMPAIGNS)})

    @app.post("/api/se/campaigns")
    def se_create_campaign():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return fail("name required")
        row = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "template_id": data.get("template_id", "t-mfa-reset"),
            "channel": data.get("channel", "email"),
            "audience": data.get("audience", "all-hands"),
            "status": "draft",  # nothing sends without explicit activation by the operator
            "created_at": time.time(),
            "sent": 0,
            "clicked": 0,
        }
        _append(_CAMPAIGNS, row)
        return ok({"campaign": row})

    @app.post("/api/se/results")
    def se_record_result():
        data = request.get_json(silent=True) or {}
        row = {
            "id": uuid.uuid4().hex[:12],
            "campaign_id": data.get("campaign_id", ""),
            "sent": int(data.get("sent", 0)),
            "opened": int(data.get("opened", 0)),
            "clicked": int(data.get("clicked", 0)),
            "reported": int(data.get("reported", 0)),
            "ts": time.time(),
        }
        _append(_RESULTS, row)
        return ok({"result": row})
