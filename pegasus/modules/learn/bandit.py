"""UCB1 over retrieval chunks and backends."""
import math

from . import db

TOTAL_SQL = "SELECT COALESCE(SUM(pulls), 0) FROM arm"


def _total() -> int:
    return db.db().execute(TOTAL_SQL).fetchone()[0] or 1


def ucb(pulls: int, wins: int) -> float:
    if pulls == 0:
        return 1e9
    return wins / pulls + math.sqrt(2 * math.log(_total()) / pulls)


def boost(arm: str) -> float:
    row = db.db().execute("SELECT pulls, wins FROM arm WHERE id=?", (arm,)).fetchone()
    if not row:
        return 1.0
    return 1.0 + 0.15 * min(ucb(row[0], row[1]), 2.0)


def hit(arm: str, win: bool) -> None:
    con = db.db()
    con.execute("INSERT INTO arm(id, pulls, wins) VALUES(?,1,?)"
                " ON CONFLICT(id) DO UPDATE SET pulls = pulls + 1,"
                " wins = wins + ?", (arm, int(win), int(win)))
    con.commit()
