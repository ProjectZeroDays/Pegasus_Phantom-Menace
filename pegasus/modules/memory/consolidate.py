"""Dedupe, supersede, reinforce."""
import time

from . import db, embed


def commit(cands: list[dict]) -> int:
    kept, con = 0, db.db()
    for c in cands:
        vec = embed.embed(c["value"])
        near = db.vec_search(vec, "fact", 1)
        if near and near[0][1] > 0.94:
            _reinforce(con, near[0][0])
            continue
        if c["kind"] == "proc":
            _upsert_proc(con, c)
            kept += 1
            continue
        _insert_fact(con, c, vec)
        kept += 1
    con.commit()
    return kept


def _insert_fact(con, c, vec) -> None:
    for row in con.execute("SELECT id FROM fact WHERE key=? AND valid_to IS NULL",
                           (c["kind"],)).fetchall():
        con.execute("UPDATE fact SET valid_to=? WHERE id=?", (time.time(), row[0]))
    confidence = c["importance"] * (0.5 if c.get("verdict") == "failed" else 1.0)
    cur = con.execute("INSERT INTO fact(key, value, valid_from, confidence, source)"
                      " VALUES(?,?,?,?,?)",
                      (c["kind"], c["value"], time.time(), confidence, c["source"]))
    con.execute("INSERT INTO vec(embedding, kind, ref_id) VALUES(?,?,?)",
                (db._blob(vec), "fact", cur.lastrowid))


def _upsert_proc(con, c) -> None:
    row = con.execute("SELECT id FROM proc WHERE signature=?", (c["signature"],)).fetchone()
    if row:
        con.execute("UPDATE proc SET uses = uses + 1 WHERE id=?", (row[0],))
        if c.get("verdict") == "pass":
            con.execute("UPDATE proc SET wins = wins + 1 WHERE id=?", (row[0],))
        return
    con.execute("INSERT INTO proc(signature, command, verdict, uses, wins)"
                " VALUES(?,?,?,1,?)",
                (c["signature"], c["command"], c.get("verdict", ""),
                 1 if c.get("verdict") == "pass" else 0))


def _reinforce(con, fact_id: int) -> None:
    con.execute("UPDATE fact SET confidence = MIN(1.0, confidence + 0.15) WHERE id=?",
                (fact_id,))
