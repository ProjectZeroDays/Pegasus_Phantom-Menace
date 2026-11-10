"""Social media intelligence routes - platform catalog, campaigns, intel store."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from flask import request

_STORE = Path.home() / ".pegasus" / "social_intel.jsonl"
_CAMPAIGNS = Path.home() / ".pegasus" / "social_campaigns.jsonl"

_PLATFORMS = [
    {"id": "twitter", "name": "X / Twitter", "status": "catalog", "osint": ["search", "timeline", "hashtags", "mentions"]},
    {"id": "linkedin", "name": "LinkedIn", "status": "catalog", "osint": ["profile", "company", "jobs"]},
    {"id": "facebook", "name": "Facebook", "status": "catalog", "osint": ["pages", "groups"]},
    {"id": "instagram", "name": "Instagram", "status": "catalog", "osint": ["public-media", "hashtags"]},
    {"id": "tiktok", "name": "TikTok", "status": "catalog", "osint": ["trending", "hashtags"]},
    {"id": "reddit", "name": "Reddit", "status": "catalog", "osint": ["search", "subreddits", "user-history"]},
    {"id": "github", "name": "GitHub", "status": "catalog", "osint": ["repos", "code-search", "commits", "advisories"]},
    {"id": "discord", "name": "Discord", "status": "catalog", "osint": ["public-servers", "invite-enumeration"]},
    {"id": "telegram", "name": "Telegram", "status": "catalog", "osint": ["public-channels", "usernames"]},
    {"id": "mastodon", "name": "Mastodon / Fediverse", "status": "catalog", "osint": ["hashtags", "instances"]},
]


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


def register(app, ok, fail):
    @app.get("/api/social-media/status")
    def social_status():
        campaigns = _load(_CAMPAIGNS)
        intel = _load(_STORE)
        active = sum(1 for c in campaigns if c.get("status") == "active")
        return ok({
            "platforms_supported": len(_PLATFORMS),
            "campaigns": len(campaigns),
            "active_campaigns": active,
            "intel_items": len(intel),
            "store": str(_STORE),
            "mode": "manual-collection (no unauthenticated scraping performed)",
        })

    @app.get("/api/social-media/platforms")
    def social_platforms():
        return ok({"platforms": _PLATFORMS})

    @app.get("/api/social-media/campaigns")
    def social_campaigns():
        return ok({"campaigns": _load(_CAMPAIGNS)})

    @app.post("/api/social-media/campaigns")
    def social_create_campaign():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return fail("name required")
        row = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "platforms": data.get("platforms") or [],
            "keywords": data.get("keywords") or [],
            "status": "active",
            "created_at": time.time(),
            "collected_intel": 0,
        }
        _append(_CAMPAIGNS, row)
        return ok({"campaign": row})

    @app.get("/api/social-media/intel")
    def social_intel():
        return ok({"intel": _load(_STORE)[-200:]})

    @app.post("/api/social-media/intel")
    def social_add_intel():
        data = request.get_json(silent=True) or {}
        text = data.get("text")
        if not text:
            return fail("text required")
        row = {
            "id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "platform": data.get("platform", "unknown"),
            "actor": data.get("actor", ""),
            "text": text[:4000],
            "tags": data.get("tags") or [],
            "severity": data.get("severity", "info"),
        }
        _append(_STORE, row)
        return ok({"intel": row})
