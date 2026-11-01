"""Nightly decay and sweep."""
import time

from . import db

HALF_LIFE = 14 * 86400
FLOOR = 0.05


def sweep() -> dict:
    con = db.db()
    now = time.time()
    con.execute("UPDATE episode SET importance = importance * exp(-(? - ts) / ?)",
                (now, HALF_LIFE))
    con.execute("DELETE FROM episode WHERE importance < ?", (FLOOR,))
    con.execute("DELETE FROM fact WHERE valid_to IS NOT NULL AND valid_to < ?",
                (now - 90 * 86400,))
    con.commit()
    return {"episodes": con.execute("SELECT COUNT(*) FROM episode").fetchone()[0],
            "facts": con.execute("SELECT COUNT(*) FROM fact WHERE valid_to IS NULL")
            .fetchone()[0]}
