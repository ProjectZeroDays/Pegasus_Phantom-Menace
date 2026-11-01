"""Command queue with TTL and single-claim semantics."""
import secrets
import time

from . import dna as dna_db

TTL = 300


def push(dna: str, command: str) -> str:
    cid = secrets.token_hex(6)
    con = dna_db._db()
    con.execute("INSERT INTO cmds VALUES(?,?,?,?,?,?,?)",
                (cid, dna, command, "queued", time.time(), None, None))
    con.commit()
    return cid


def take(dna: str) -> tuple[str, str] | None:
    con = dna_db._db()
    con.execute("UPDATE cmds SET state='expired' WHERE state='queued' AND created < ?",
                (time.time() - TTL,))
    row = con.execute("SELECT id, body FROM cmds WHERE dna=? AND state='queued'"
                      " ORDER BY created LIMIT 1", (dna,)).fetchone()
    if not row:
        con.commit()
        return None
    con.execute("UPDATE cmds SET state='delivered', delivered=? WHERE id=?",
                (time.time(), row[0]))
    con.commit()
    return row[0], row[1]


def complete(cid: str, result: str) -> None:
    con = dna_db._db()
    con.execute("UPDATE cmds SET state='done', result=? WHERE id=?", (result[:20000], cid))
    con.commit()
