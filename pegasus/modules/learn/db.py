"""Trace store."""
import pathlib
import sqlite3

DB = pathlib.Path.home() / ".pegasus" / "traces.db"


def db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS trace(id INTEGER PRIMARY KEY, ts REAL,"
                " role TEXT, prompt TEXT, response TEXT, verdict TEXT, backend TEXT,"
                " model TEXT, case_id TEXT)")
    return con


def rows(sql: str, args=()) -> list[dict]:
    con = db()
    cur = con.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
