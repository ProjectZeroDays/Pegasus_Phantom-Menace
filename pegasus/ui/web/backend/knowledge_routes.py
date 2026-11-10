"""Knowledge surfaces: wiki, help, how-to, bug reports and starring.

The wiki and how-to content ships with the repository under
``pegasus/ui/web/backend/content``.  Operator notes, starred entries and bug
reports live in ``~/.pegasus`` so they survive reinstalls.
"""
from __future__ import annotations

import json
import pathlib
import re
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.auth import operator

CONTENT_DIR = pathlib.Path(__file__).resolve().parent / "content"
NOTES_FILE = pathlib.Path.home() / ".pegasus" / "knowledge_notes.json"
REPORTS_FILE = pathlib.Path.home() / ".pegasus" / "bug_reports.json"
STARS_FILE = pathlib.Path.home() / ".pegasus" / "stars.json"
REPO = "ProjectZeroDays/Pegasus_Phantom-Menace"

_slug = re.compile(r"[^a-z0-9._-]+")


def _read(path: pathlib.Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _slugify(text: str) -> str:
    return _slug.sub("-", (text or "").strip().lower()).strip("-")


def _collection(name: str) -> List[Dict[str, Any]]:
    folder = CONTENT_DIR / name
    if not folder.is_dir():
        return []
    items = []
    for path in sorted(folder.glob("*.md")):
        try:
            body = path.read_text(encoding="utf-8")
        except Exception:
            body = ""
        title = ""
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        items.append({
            "id": path.stem,
            "title": title or path.stem.replace("-", " ").title(),
            "summary": next((l.strip() for l in body.splitlines()
                             if l.strip() and not l.startswith("#")), ""),
            "body": body,
            "section": name,
        })
    return items


def register(app, ok, fail):
    @app.get("/api/wiki")
    @operator.require("viewer")
    def wiki_index():
        items = _collection("wiki")
        stars = _read(STARS_FILE, {})
        for item in items:
            item["starred"] = bool(stars.get(f"wiki:{item['id']}"))
        return ok({"entries": items, "count": len(items)})

    @app.get("/api/wiki/<entry_id>")
    @operator.require("viewer")
    def wiki_entry(entry_id: str):
        item = next((i for i in _collection("wiki") if i["id"] == entry_id), None)
        if not item:
            return fail("entry not found", 404)
        return ok({"entry": item})

    @app.get("/api/help")
    @operator.require("viewer")
    def help_index():
        items = _collection("help")
        stars = _read(STARS_FILE, {})
        for item in items:
            item["starred"] = bool(stars.get(f"help:{item['id']}"))
        return ok({"entries": items, "count": len(items)})

    @app.get("/api/howto")
    @operator.require("viewer")
    def howto_index():
        items = _collection("howto")
        stars = _read(STARS_FILE, {})
        for item in items:
            item["starred"] = bool(stars.get(f"howto:{item['id']}"))
        return ok({"entries": items, "count": len(items)})

    @app.get("/api/knowledge/notes")
    @operator.require("viewer")
    def notes_list():
        op = operator.current()
        store = _read(NOTES_FILE, {})
        return ok({"notes": store.get(op["user"], [])})

    @app.post("/api/knowledge/notes")
    @operator.require("operator")
    def notes_add():
        op = operator.current()
        body = request.get_json(silent=True) or {}
        text = (body.get("text") or "").strip()
        if not text:
            return fail("note text required")
        store = _read(NOTES_FILE, {})
        items = store.setdefault(op["user"], [])
        entry = {"id": len(items) + 1, "text": text,
                 "topic": body.get("topic") or "general",
                 "created": time.time()}
        items.append(entry)
        _write(NOTES_FILE, store)
        return ok({"note": entry})

    @app.delete("/api/knowledge/notes/<int:note_id>")
    @operator.require("operator")
    def notes_delete(note_id: int):
        op = operator.current()
        store = _read(NOTES_FILE, {})
        items = store.setdefault(op["user"], [])
        before = len(items)
        items[:] = [i for i in items if i.get("id") != note_id]
        if len(items) == before:
            return fail("note not found", 404)
        _write(NOTES_FILE, store)
        return ok({"deleted": True})

    @app.post("/api/bug-reports")
    @operator.require("viewer")
    def bug_report_create():
        op = operator.current()
        body = request.get_json(silent=True) or {}
        title = (body.get("title") or "").strip()
        if not title:
            return fail("title required")
        report = {
            "id": secrets_token(),
            "title": title,
            "description": body.get("description") or "",
            "severity": body.get("severity") or "normal",
            "component": body.get("component") or "console",
            "reporter": op["user"],
            "created": time.time(),
            "status": "open",
        }
        store = _read(REPORTS_FILE, [])
        store.append(report)
        _write(REPORTS_FILE, store)
        return ok({"report": report})

    @app.get("/api/bug-reports")
    @operator.require("viewer")
    def bug_report_list():
        reports = _read(REPORTS_FILE, [])
        return ok({"reports": reports})

    @app.get("/api/stars")
    @operator.require("viewer")
    def stars_list():
        stars = _read(STARS_FILE, {})
        return ok({"stars": [{"key": k, "created": v} for k, v in stars.items()]})

    @app.post("/api/stars")
    @operator.require("viewer")
    def stars_toggle():
        body = request.get_json(silent=True) or {}
        key = (body.get("key") or "").strip()
        if not key:
            return fail("key required")
        stars = _read(STARS_FILE, {})
        if key in stars:
            stars.pop(key)
            starred = False
        else:
            stars[key] = time.time()
            starred = True
        _write(STARS_FILE, stars)
        return ok({"key": key, "starred": starred})

    @app.get("/api/stars/repository")
    @operator.require("viewer")
    def repo_star():
        """Read the public star count for the project repository."""
        url = f"https://api.github.com/repos/{REPO}"
        try:
            from urllib import request as urlrequest
            with urlrequest.urlopen(url, timeout=6) as resp:
                data = json.loads(resp.read().decode())
            return ok({"repository": REPO, "stars": data.get("stargazers_count"),
                       "forks": data.get("forks_count"),
                       "open_issues": data.get("open_issues_count")})
        except Exception as exc:  # noqa: BLE001
            return ok({"repository": REPO, "stars": None, "error": str(exc)[:160]})


def secrets_token() -> str:
    import secrets
    return secrets.token_hex(8)
