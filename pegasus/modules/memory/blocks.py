"""Bounded working memory. Oldest line drops on overflow."""
from . import db

CAPS = {"case": 300, "host": 250, "operator": 150}


def _trim(body: str, cap: int) -> str:
    lines = body.splitlines()
    while len(" ".join(lines).split()) > cap and len(lines) > 1:
        lines.pop(0)
    return "\n".join(lines)


def write(name: str, case_id: str, body: str) -> None:
    import time
    con = db.db()
    con.execute("INSERT OR REPLACE INTO block VALUES(?,?,?,?)",
                (name, case_id, _trim(body, CAPS.get(name, 200)), time.time()))
    con.commit()


def read(name: str, case_id: str) -> str:
    row = db.db().execute("SELECT body FROM block WHERE name=? AND case_id=?",
                          (name, case_id)).fetchone()
    return row[0] if row else ""


def render(case_id: str) -> str:
    out = []
    for name in CAPS:
        body = read(name, case_id)
        if body:
            out.append(f"<{name}>\n{body}\n</{name}>")
    return "\n".join(out)


def all_blocks(case_id: str) -> dict:
    return {name: read(name, case_id) for name in CAPS}
