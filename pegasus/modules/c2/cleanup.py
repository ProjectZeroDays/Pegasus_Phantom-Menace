"""Nightly DNA and command sweep."""
import time

from . import dna as dna_db, ratelimit


def sweep(days: int = 30) -> dict:
    con = dna_db._db()
    dead = [r[0] for r in con.execute("SELECT dna FROM dna WHERE last_seen < ?",
                                      (time.time() - days * 86400,))]
    con.executemany("DELETE FROM dna WHERE dna=?", [(d,) for d in dead])
    con.execute("DELETE FROM cmds WHERE state IN ('done','expired') AND created < ?",
                (time.time() - 7 * 86400,))
    con.commit()
    for d in dead:
        ratelimit.forget(f"beacon:{d}")
    return {"dna_removed": len(dead)}
