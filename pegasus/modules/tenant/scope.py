"""Org scoping and identifier extraction for prompt scrubbing."""
import pathlib
import sqlite3
import time
import uuid

DB = pathlib.Path.home() / ".pegasus" / "tenants.db"


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS orgs(id TEXT PRIMARY KEY, name TEXT,"
                " created REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS members(org_id TEXT, user TEXT, role TEXT,"
                " PRIMARY KEY(org_id, user))")
    con.execute("CREATE TABLE IF NOT EXISTS idents(org_id TEXT, value TEXT,"
                " PRIMARY KEY(org_id, value))")
    return con


def create(name: str) -> str:
    org_id = str(uuid.uuid4())
    con = _db()
    con.execute("INSERT INTO orgs VALUES(?,?,?)", (org_id, name, time.time()))
    con.commit()
    return org_id


def add(org_id: str, user: str, role: str = "operator") -> None:
    con = _db()
    con.execute("INSERT OR REPLACE INTO members VALUES(?,?,?)", (org_id, user, role))
    con.commit()


def remember(org_id: str, values: list[str]) -> None:
    con = _db()
    for value in values:
        if value:
            con.execute("INSERT OR IGNORE INTO idents VALUES(?,?)", (org_id, value))
    con.commit()


def identifiers(org_id: str) -> list[str]:
    return [r[0] for r in _db().execute("SELECT value FROM idents WHERE org_id=?",
                                        (org_id,))]
