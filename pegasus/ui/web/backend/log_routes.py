"""Log dashboard + log file routes.

Serves the Pegasus event stream (``events.jsonl``) and the on-disk log files
that back it.  The GUI's Logs page and the Logs Dashboard both read from here.

Path resolution is portable: the configured workspace logs directory wins, then
the repository ``log/`` directory, then the user home ``~/.pegasus/logs``.  No
machine-specific absolute paths are baked in.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import request, send_file

_MAX_EVENTS = 5000
_MAX_TAIL_BYTES = 512 * 1024

_LEVEL_RE = re.compile(r"\b(CRITICAL|FATAL|ERROR|WARNING|WARN|INFO|DEBUG|TRACE)\b")


def _repo_root() -> Path:
    # pegasus/ui/web/backend/log_routes.py -> repo root
    return Path(__file__).resolve().parents[4]


def _candidate_dirs() -> List[Path]:
    dirs: List[Path] = []
    try:
        from pegasus.core.config import get_settings

        dirs.append(Path(get_settings().get_logs_dir()))
    except Exception:
        pass
    dirs.append(_repo_root() / "log")
    dirs.append(_repo_root() / "logs")
    dirs.append(Path.home() / ".pegasus" / "logs")
    dirs.append(Path.home() / ".pegasus" / "log")
    seen: set[str] = set()
    out: List[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _log_dir() -> Path:
    """Pick the directory that actually holds the event stream.

    Preference: the first candidate that contains an events file, otherwise the
    first candidate that exists at all.  This keeps the console pointed at the
    real event stream even when several log directories are present.
    """
    candidates = _candidate_dirs()
    for d in candidates:
        if _events_file(d) is not None:
            return d
    for d in candidates:
        if d.is_dir():
            return d
    return _repo_root() / "log"


def _events_file(directory: Path) -> Optional[Path]:
    for name in ("events.jsonl", "events.log", "events.json"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _log_files(directory: Path) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    if not directory.is_dir():
        return files
    for path in sorted(directory.rglob("*")):
        try:
            if not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        files.append({
            "id": path.relative_to(directory).as_posix(),
            "name": path.name,
            "dir": str(directory),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        })
    files.sort(key=lambda f: f["modified"], reverse=True)
    return files


def _read_events(path: Optional[Path], limit: int = _MAX_EVENTS) -> List[Dict[str, Any]]:
    """Parse the JSONL event stream defensively; bad lines are counted, not fatal."""
    events: List[Dict[str, Any]] = []
    if not path or not path.is_file():
        return events
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return events
    for line in raw.splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            events.append(row)
    return events


def _classify(text: str) -> str:
    m = _LEVEL_RE.search(text.upper())
    if not m:
        return "info"
    level = m.group(1)
    if level in ("CRITICAL", "FATAL"):
        return "critical"
    if level == "ERROR":
        return "error"
    if level in ("WARNING", "WARN"):
        return "warning"
    if level in ("DEBUG", "TRACE"):
        return "debug"
    return "info"


def _summarise(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    categories: Dict[str, int] = {}
    levels: Dict[str, int] = {"critical": 0, "error": 0, "warning": 0, "info": 0, "debug": 0}
    statuses: Dict[str, int] = {}
    timeline: List[Dict[str, Any]] = []
    total = 0

    for event in events:
        total += 1
        name = str(event.get("event") or "unknown")
        categories[name] = categories.get(name, 0) + 1
        status = str(event.get("status") or "").strip()
        if status:
            statuses[status.upper()] = statuses.get(status.upper(), 0) + 1
        note = str(event.get("note") or "")
        level = _classify(f"{status} {note}")
        levels[level] = levels.get(level, 0) + 1
        timeline.append({
            "ts": event.get("ts") or "",
            "event": name,
            "status": status or level,
            "note": note[:280],
            "file": event.get("file") or "",
            "level": level,
        })

    timeline.sort(key=lambda t: str(t.get("ts") or ""), reverse=True)
    top = sorted(categories.items(), key=lambda kv: kv[1], reverse=True)[:12]
    return {
        "total": total,
        "categories": categories,
        "levels": levels,
        "statuses": statuses,
        "topCategories": [{"name": n, "count": c} for n, c in top],
        "timeline": timeline[:400],
    }


def register(app, ok, fail):
    @app.get("/api/logs")
    def logs_index():
        directory = _log_dir()
        files = _log_files(directory)
        events = _read_events(_events_file(directory))
        summary = _summarise(events)
        return ok({
            "files": files,
            "logs": files,                      # legacy key used by Logs.tsx
            "count": len(files),
            "directory": str(directory),
            "main": summary["total"],
            "categories": summary["categories"],
            "dashboard": summary["categories"],
            "levels": summary["levels"],
            "statuses": summary["statuses"],
            "topCategories": summary["topCategories"],
            "timeline": summary["timeline"],
            "eventsFile": str(_events_file(directory) or ""),
        })

    @app.get("/api/logs/dashboard")
    def logs_dashboard():
        directory = _log_dir()
        files = _log_files(directory)
        events = _read_events(_events_file(directory))
        summary = _summarise(events)
        return ok({
            "directory": str(directory),
            "eventsFile": str(_events_file(directory) or ""),
            "fileCount": len(files),
            "totalBytes": sum(f["size"] for f in files),
            "files": files[:50],
            **summary,
        })

    @app.get("/api/logs/<path:log_id>")
    def logs_file(log_id: str):
        directory = _log_dir()
        target = (directory / log_id).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            return fail("invalid log id", 400)
        if not target.is_file():
            return fail("log not found", 404)
        try:
            data = target.read_bytes()
        except OSError as exc:
            return fail(f"unreadable log: {exc}", 500)
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        return ok({
            "id": log_id,
            "name": target.name,
            "size": len(data),
            "modified": target.stat().st_mtime,
            "totalLines": len(lines),
            "content": "\n".join(lines[-4000:]),
        })

    @app.get("/api/logs/<path:log_id>/download")
    def logs_download(log_id: str):
        directory = _log_dir()
        target = (directory / log_id).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            return fail("invalid log id", 400)
        if not target.is_file():
            return fail("log not found", 404)
        return send_file(str(target), as_attachment=True, download_name=target.name)

    @app.get("/api/logs/combined/download")
    def logs_combined_download():
        directory = _log_dir()
        chunks: List[str] = []
        for meta in _log_files(directory):
            path = directory / meta["id"]
            try:
                chunks.append(f"===== {meta['id']} =====\n")
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
        body = "\n".join(chunks)
        return ok({"content": body, "bytes": len(body.encode('utf-8', errors='ignore'))})

    @app.delete("/api/logs/<path:log_id>")
    def logs_delete(log_id: str):
        directory = _log_dir()
        target = (directory / log_id).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            return fail("invalid log id", 400)
        if not target.is_file():
            return fail("log not found", 404)
        try:
            target.unlink()
        except OSError as exc:
            return fail(f"delete failed: {exc}", 500)
        return ok({"deleted": True, "id": log_id})
