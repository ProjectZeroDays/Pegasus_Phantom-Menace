"""Append-only run journal. Survives restart so a crashed chain resumes."""
import json
import pathlib
import sqlite3
import time

DB = pathlib.Path.home() / ".pegasus" / "journal.db"


def _con() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, run_id TEXT,"
                " ts REAL, phase TEXT, message TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_run ON events(run_id)")
    return con


def append(run_id: str, phase: str, message: str) -> None:
    con = _con()
    con.execute("INSERT INTO events(run_id, ts, phase, message) VALUES(?,?,?,?)",
                (run_id, time.time(), phase, message))
    con.commit()


def phase(run_id: str, name: str) -> None:
    append(run_id, name, "phase-enter")


def step(run_id: str, name: str) -> None:
    append(run_id, "post", f"step:{name}")


def replay(run_id: str) -> list[dict]:
    rows = _con().execute("SELECT ts, phase, message FROM events WHERE run_id=?"
                          " ORDER BY id", (run_id,)).fetchall()
    return [{"ts": r[0], "phase": r[1], "message": r[2]} for r in rows]


def completed_steps(run_id: str) -> set[str]:
    return {r["message"].split(":", 1)[1] for r in replay(run_id)
            if r["message"].startswith("step:")}


def purge(run_id: str) -> None:
    con = _con()
    con.execute("DELETE FROM events WHERE run_id=?", (run_id,))
    con.commit()


def archive(run_id: str, dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(replay(run_id), indent=2))
