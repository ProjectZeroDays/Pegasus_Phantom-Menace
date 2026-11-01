"""Weighted hybrid recall with MMR and a hard token budget."""
import time

from . import db, embed

HALF_LIFE = 14 * 86400
MMR = 0.85


def recall(query: str, case_id: str, budget: int = 900) -> str:
    vec = embed.embed(query)
    scored: list[tuple[dict, float, list[float]]] = []
    for ref_id, sim in db.vec_search(vec, "fact", 40):
        row = _fact(ref_id)
        if row:
            scored.append((row, 0.6 * sim + 0.4 * row["confidence"], vec))
    for row in _fts(query, 20):
        scored.append((row, 0.5, []))
    picked, seen, tokens = [], set(), 0
    for row, score, rvec in sorted(scored, key=lambda r: -r[1]):
        if row["id"] in seen:
            continue
        if rvec and any(_cos(rvec, p[2]) > MMR for p in picked if p[2]):
            continue
        line = f"{row['key']}: {row['value']}"
        tokens += len(line.split())
        if tokens > budget:
            break
        picked.append((row, score, rvec))
        seen.add(row["id"])
    _bump([p[0]["id"] for p in picked])
    return "\n".join(f"- {p[0]['key']}: {p[0]['value']}" for p in picked)


def _fact(ref_id: int) -> dict | None:
    con = db.db()
    row = con.execute("SELECT id, key, value, confidence, valid_to FROM fact WHERE id=?",
                      (ref_id,)).fetchone()
    if not row:
        return None
    return {"id": row[0], "key": row[1], "value": row[2],
            "confidence": row[3] * (1.0 if row[4] is None else 0.5)}


def _fts(query: str, k: int) -> list[dict]:
    con = db.db()
    try:
        rows = con.execute("SELECT rowid, body FROM mem_fts WHERE mem_fts MATCH ? LIMIT ?",
                           (query, k)).fetchall()
    except Exception:
        return []
    return [{"id": -r[0], "key": "note", "value": r[1], "confidence": 0.4} for r in rows]


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _bump(ids: list[int]) -> None:
    con = db.db()
    for fact_id in ids:
        if fact_id > 0:
            con.execute("UPDATE fact SET confidence = MIN(1.0, confidence + 0.05)"
                        " WHERE id=?", (fact_id,))
    con.commit()
