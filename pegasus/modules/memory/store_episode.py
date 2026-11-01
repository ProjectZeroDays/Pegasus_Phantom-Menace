"""Episode writes, kept separate so routes stays thin."""
import time

from . import db


def add(case_id: str, host: str, kind: str, body: str, importance: float = 0.5) -> int:
    con = db.db()
    cur = con.execute("INSERT INTO episode(ts, case_id, host, kind, body, importance)"
                      " VALUES(?,?,?,?,?,?)",
                      (time.time(), case_id, host, kind, body[:4000], importance))
    con.execute("INSERT INTO mem_fts(rowid, body) VALUES(?,?)", (cur.lastrowid, body[:4000]))
    con.commit()
    return cur.lastrowid
