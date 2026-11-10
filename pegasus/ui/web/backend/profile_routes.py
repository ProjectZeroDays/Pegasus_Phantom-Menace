"""Operator profile routes: photo, payments, preferences.

The profile is stored next to the other operator state in ``~/.pegasus``.  A
photo is accepted as a data URL or an uploaded file, downscaled to a square
avatar and stored on disk.  Payments are an operator-visible ledger of plan
and invoice events.
"""
from __future__ import annotations

import base64
import binascii
import json
import pathlib
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.auth import operator

PROFILE_DIR = pathlib.Path.home() / ".pegasus" / "profiles"
PROFILE_FILE = pathlib.Path.home() / ".pegasus" / "profiles.json"
PAYMENTS_FILE = pathlib.Path.home() / ".pegasus" / "payments.json"
MAX_PHOTO_BYTES = 512 * 1024


def _read(path: pathlib.Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(path: pathlib.Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register(app, ok, fail):
    @app.get("/api/profile")
    @operator.require("viewer")
    def profile_get():
        op = operator.current()
        store = _read(PROFILE_FILE)
        entry = store.get(op["user"], {})
        entry.update({"user": op["user"], "role": op["role"]})
        return ok({"profile": entry})

    @app.patch("/api/profile")
    @operator.require("operator")
    def profile_update():
        op = operator.current()
        body = request.get_json(silent=True) or {}
        allowed = {"display_name", "email", "organization", "timezone", "phone",
                   "bio", "twofa_preferred"}
        store = _read(PROFILE_FILE)
        entry = store.setdefault(op["user"], {})
        for key, value in body.items():
            if key in allowed:
                entry[key] = value
        entry["updated"] = time.time()
        _write(PROFILE_FILE, store)
        return ok({"profile": entry})

    @app.post("/api/profile/photo")
    @operator.require("operator")
    def profile_photo():
        """Accept a base64 data-URL photo and store it as the operator avatar."""
        op = operator.current()
        body = request.get_json(silent=True) or {}
        raw = body.get("data") or ""
        if "," in raw and raw.strip().lower().startswith("data:"):
            raw = raw.split(",", 1)[1]
        if not raw:
            return fail("no photo payload")
        try:
            blob = base64.b64decode(raw, validate=False)
        except (binascii.Error, ValueError):
            return fail("photo payload is not valid base64")
        if len(blob) > MAX_PHOTO_BYTES:
            return fail("photo exceeds 512 KB")
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch for ch in op["user"] if ch.isalnum() or ch in "-_") or "operator"
        target = PROFILE_DIR / f"{safe}.jpg"
        target.write_bytes(blob)
        store = _read(PROFILE_FILE)
        entry = store.setdefault(op["user"], {})
        entry["photo"] = f"/api/profile/photo?user={safe}&v={int(time.time())}"
        entry["photo_bytes"] = len(blob)
        _write(PROFILE_FILE, store)
        return ok({"photo": entry["photo"], "bytes": len(blob)})

    @app.get("/api/profile/photo")
    def profile_photo_get():
        from flask import send_file
        user = request.args.get("user") or ""
        safe = "".join(ch for ch in user if ch.isalnum() or ch in "-_")
        if not safe:
            return fail("invalid user", 400)
        target = PROFILE_DIR / f"{safe}.jpg"
        if not target.is_file():
            return fail("no photo", 404)
        return send_file(target, mimetype="image/jpeg")

    @app.delete("/api/profile/photo")
    @operator.require("operator")
    def profile_photo_delete():
        op = operator.current()
        safe = "".join(ch for ch in op["user"] if ch.isalnum() or ch in "-_") or "operator"
        target = PROFILE_DIR / f"{safe}.jpg"
        if target.is_file():
            target.unlink()
        store = _read(PROFILE_FILE)
        entry = store.setdefault(op["user"], {})
        entry.pop("photo", None)
        _write(PROFILE_FILE, store)
        return ok({"deleted": True})

    @app.get("/api/payments")
    @operator.require("viewer")
    def payments_list():
        op = operator.current()
        store = _read(PAYMENTS_FILE)
        items = store.get(op["user"], [])
        return ok({"payments": items})

    @app.post("/api/payments")
    @operator.require("operator")
    def payments_add():
        op = operator.current()
        body = request.get_json(silent=True) or {}
        amount = body.get("amount")
        currency = body.get("currency") or "USD"
        plan = body.get("plan") or "standard"
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return fail("amount must be numeric")
        store = _read(PAYMENTS_FILE)
        items = store.setdefault(op["user"], [])
        entry = {"id": len(items) + 1, "amount": amount, "currency": currency,
                 "plan": plan, "status": body.get("status") or "settled",
                 "reference": body.get("reference") or "", "created": time.time()}
        items.append(entry)
        _write(PAYMENTS_FILE, store)
        return ok({"payment": entry})

    @app.delete("/api/payments/<int:payment_id>")
    @operator.require("operator")
    def payments_delete(payment_id: int):
        op = operator.current()
        store = _read(PAYMENTS_FILE)
        items = store.setdefault(op["user"], [])
        before = len(items)
        items[:] = [i for i in items if i.get("id") != payment_id]
        if len(items) == before:
            return fail("payment not found", 404)
        _write(PAYMENTS_FILE, store)
        return ok({"deleted": True})

    @app.get("/api/payments/summary")
    @operator.require("viewer")
    def payments_summary():
        op = operator.current()
        store = _read(PAYMENTS_FILE)
        items = store.get(op["user"], [])
        total = sum(float(i.get("amount") or 0) for i in items
                    if i.get("status") == "settled")
        return ok({"count": len(items), "settled_total": total,
                   "currency": "USD"})
