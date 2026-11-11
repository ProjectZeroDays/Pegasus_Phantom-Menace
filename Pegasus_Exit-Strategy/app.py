"""Pegasus Exit Strategy - engagement close-out console.

A focused fork of Pegasus Phantom Menace that covers the last mile of an
engagement: teardown, evidence hand-over, access revocation and the written
close-out.  It reuses the original Pegasus identity and colour tokens.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
from typing import Any, Dict, List

STATE_DIR = pathlib.Path.home() / ".pegasus" / "exit-strategy"
STATE_FILE = STATE_DIR / "state.json"

# The original Pegasus palette.
COLORS = {
    "primary": "#ff3d00",
    "primary_soft": "#bf3600",
    "secondary": "#58a6ff",
    "background": "#0a0b0e",
    "surface": "#10141b",
    "line": "#30363d",
    "ink": "#e6edf3",
    "muted": "#8b949e",
}

CHECKLIST: List[Dict[str, Any]] = [
    {"id": "access-revoked", "group": "Access",
     "title": "Revoke the access that was opened",
     "detail": "API keys, VPN profiles, SOCKS endpoints and tunnel tokens issued "
               "for the engagement are rotated or revoked."},
    {"id": "devices-clean", "group": "Access",
     "title": "Return the test devices to their original state",
     "detail": "Uninstall the tooling that was installed, remove the test "
               "accounts, confirm no debug bridge is left enabled."},
    {"id": "evidence-inventory", "group": "Evidence",
     "title": "Complete the evidence inventory",
     "detail": "Every artefact has a location, a hash and a named holder."},
    {"id": "evidence-handover", "group": "Evidence",
     "title": "Hand the evidence over",
     "detail": "The client has the copies they are entitled to, and the chain "
               "of custody is written down."},
    {"id": "logs-purged", "group": "Evidence",
     "title": "Purge the working copies that must not be retained",
     "detail": "Local captures and scratch evidence are removed where the "
               "engagement terms require it."},
    {"id": "report-written", "group": "Reporting",
     "title": "Write the close-out report",
     "detail": "Findings, remediation, what was tried, what was in scope and "
               "what was deliberately left alone."},
    {"id": "retest-scheduled", "group": "Reporting",
     "title": "Agree the retest",
     "detail": "The client knows when the fixes will be verified and what "
               "evidence that retest will produce."},
    {"id": "scope-lifted", "group": "Reporting",
     "title": "Lift the access and the authorisations",
     "detail": "Temporary accounts, whitelists and third-party access are "
               "closed and confirmed."},
]

REPORT_SECTIONS = ["Scope", "Methodology", "Findings", "Remediation",
                   "Evidence index", "Retest plan"]


def _read() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"done": {}, "notes": [], "updated": 0}


def _write(data: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def state() -> Dict[str, Any]:
    data = _read()
    done = data.get("done", {})
    items = [dict(item, done=bool(done.get(item["id"]))) for item in CHECKLIST]
    completed = sum(1 for item in items if item["done"])
    return {
        "items": items,
        "completed": completed,
        "total": len(items),
        "notes": data.get("notes", []),
        "report_sections": REPORT_SECTIONS,
        "colors": COLORS,
        "updated": data.get("updated", 0),
    }


def toggle(item_id: str) -> Dict[str, Any]:
    data = _read()
    done = data.setdefault("done", {})
    done[item_id] = not done.get(item_id, False)
    data["updated"] = time.time()
    _write(data)
    return state()


def add_note(text: str) -> Dict[str, Any]:
    data = _read()
    notes = data.setdefault("notes", [])
    notes.append({"id": len(notes) + 1, "text": text, "created": time.time()})
    data["updated"] = time.time()
    _write(data)
    return state()


def build_app():
    from flask import Flask, jsonify, request

    app = Flask(__name__, static_folder="assets", static_url_path="/assets")

    @app.get("/")
    def index():
        from flask import send_file
        page = pathlib.Path(__file__).resolve().parent / "index.html"
        if not page.is_file():
            return jsonify({"ok": False, "error": "console shell missing"}), 500
        return send_file(page)

    @app.get("/api/state")
    def api_state():
        return jsonify({"ok": True, "data": state()})

    @app.post("/api/toggle")
    def api_toggle():
        body = request.get_json(silent=True) or {}
        item_id = body.get("id") or ""
        if not any(item["id"] == item_id for item in CHECKLIST):
            return jsonify({"ok": False, "error": "unknown item"}), 400
        return jsonify({"ok": True, "data": toggle(item_id)})

    @app.post("/api/notes")
    def api_notes():
        body = request.get_json(silent=True) or {}
        text = str(body.get("text") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "note text required"}), 400
        return jsonify({"ok": True, "data": add_note(text)})

    return app


def main() -> int:
    parser = argparse.ArgumentParser(prog="pegasus-exit-strategy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5098)
    args = parser.parse_args()
    app = build_app()
    print(f"Pegasus Exit Strategy on http://{args.host}:{args.port}/")
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
