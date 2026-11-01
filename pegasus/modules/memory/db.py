"""sqlite + sqlite-vec connection."""
import pathlib
import sqlite3

import sqlite_vec

DB = pathlib.Path.home() / ".pegasus" / "memory.db"
SCHEMA = pathlib.Path(__file__).with_name("0001.sql")
DIM = 384


def db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    if not con.execute("SELECT name FROM sqlite_master WHERE name='fact'").fetchone():
        con.executescript(SCHEMA.read_text())
    return con


def vec_insert(kind: str, ref_id: int, vec: list[float]) -> None:
    con = db()
    con.execute("INSERT INTO vec(embedding, kind, ref_id) VALUES(?,?,?)",
                (_blob(vec), kind, ref_id))
    con.commit()


def vec_search(vec: list[float], kind: str, k: int) -> list[tuple[int, float]]:
    con = db()
    rows = con.execute("SELECT ref_id, distance FROM vec WHERE embedding MATCH ? "
                       "AND kind = ? ORDER BY distance LIMIT ?",
                       (_blob(vec), kind, k)).fetchall()
    return [(r[0], 1.0 - r[1]) for r in rows]


def _blob(vec: list[float]) -> bytes:
    import struct
    return struct.pack(f"{len(vec)}f", *vec)
