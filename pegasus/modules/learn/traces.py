"""Accepted-run capture."""
import time

from . import db

MIN_SFT = 2000


def record(role, prompt, response, verdict, backend, model, case_id=None) -> None:
    con = db.db()
    con.execute("INSERT INTO trace(ts, role, prompt, response, verdict, backend, model,"
                " case_id) VALUES(?,?,?,?,?,?,?,?)",
                (time.time(), str(role), prompt, response, verdict, backend, model,
                 case_id))
    con.commit()


def accepted(role: str, limit: int = 5000) -> list[dict]:
    return db.rows("SELECT * FROM trace WHERE role=? AND verdict='pass'"
                   " ORDER BY ts DESC LIMIT ?", (str(role), limit))
