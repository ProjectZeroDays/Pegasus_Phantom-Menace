"""Delivery receipts. A send without one is a gap."""
import json
import pathlib
import re
import sqlite3
import time

DB = pathlib.Path.home() / ".pegasus" / "receipts.db"


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY, run_id TEXT,"
                " ts REAL, channel TEXT, kind TEXT, target TEXT, via TEXT, ref TEXT,"
                " error TEXT)")
    return con


def _mask(target: str) -> str:
    digits = re.sub(r"\D", "", target)
    if len(digits) < 8:
        return target
    return f"+{digits[:-4]}xxxx{digits[-4:]}"


def record(run_id, channel, kind, target, result, error=None) -> dict:
    via = "error" if error else (result.get("via") or
                                 ("link" if result.get("link") else "sent"))
    row = {"ts": time.time(), "channel": channel, "kind": kind,
           "target": _mask(target), "via": via,
           "ref": result.get("sent") or result.get("link"), "error": error}
    con = _db()
    con.execute("INSERT INTO receipts(run_id, ts, channel, kind, target, via, ref, error)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (run_id, row["ts"], channel, kind, row["target"], via, row["ref"], error))
    con.commit()
    if run_id:
        try:
            from ..autonomous import journal
            journal.append(run_id, "delivery", json.dumps(row))
        except Exception:
            pass
    return row


def list_for(run_id: str | None, limit: int = 200) -> list[dict]:
    con = _db()
    if run_id:
        rows = con.execute("SELECT ts, channel, kind, target, via, ref, error FROM receipts"
                           " WHERE run_id=? ORDER BY id DESC LIMIT ?", (run_id, limit))
    else:
        rows = con.execute("SELECT ts, channel, kind, target, via, ref, error FROM receipts"
                           " ORDER BY id DESC LIMIT ?", (limit,))
    cols = ("ts", "channel", "kind", "target", "via", "ref", "error")
    return [dict(zip(cols, r)) for r in rows.fetchall()]
