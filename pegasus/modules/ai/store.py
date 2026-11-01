"""Turn store. 30-day retention, identifier scrubbing."""
import json
import pathlib
import sqlite3
import time

DB = pathlib.Path.home() / ".pegasus" / "turns.db"
RETENTION = 30 * 86400


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS turns(id INTEGER PRIMARY KEY, ts REAL, role TEXT,"
                " prompt TEXT, response TEXT, backend TEXT, model TEXT, verdict TEXT,"
                " case_id TEXT)")
    return con


def record(role, prompt, response, backend, model, verdict, case_id=None) -> None:
    con = _db()
    con.execute("INSERT INTO turns(ts, role, prompt, response, backend, model, verdict,"
                " case_id) VALUES(?,?,?,?,?,?,?,?)",
                (time.time(), str(role), prompt[:8000], response[:8000], backend,
                 model, verdict, case_id))
    con.execute("DELETE FROM turns WHERE ts < ?", (time.time() - RETENTION,))
    con.commit()


def scrub(text: str, case_id: str | None) -> str:
    if not case_id:
        return text
    for token in identifiers(case_id):
        text = text.replace(token, "<id>")
    return text


def identifiers(case_id: str) -> list[str]:
    try:
        from ..tenant import scope
        return scope.identifiers(case_id)
    except Exception:
        return []


def turns(case_id: str | None = None, limit: int = 200) -> list[dict]:
    con = _db()
    if case_id:
        rows = con.execute("SELECT ts, role, prompt, response, backend, verdict FROM turns"
                           " WHERE case_id=? ORDER BY id DESC LIMIT ?",
                           (case_id, limit)).fetchall()
    else:
        rows = con.execute("SELECT ts, role, prompt, response, backend, verdict FROM turns"
                           " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(zip(("ts", "role", "prompt", "response", "backend", "verdict"), r))
            for r in rows]


def export(case_id: str, path: pathlib.Path) -> None:
    path.write_text(json.dumps(turns(case_id, 10000), indent=2))
