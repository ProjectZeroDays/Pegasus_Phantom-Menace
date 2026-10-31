#!/usr/bin/env python3
"""Link-out landing — one URL, UA-sniffed artifact, hit logging."""
from __future__ import annotations
import json
import pathlib
import secrets
import sqlite3
import time

DB = pathlib.Path.home() / ".pegasus" / "landing.db"

UA_RULES = [
    (("android",), "apk"),
    (("iphone", "ipad", "ios"), "pdf"),
    (("windows", "macintosh", "linux"), "pdf"),
]


def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS links(
        token TEXT PRIMARY KEY, artifacts TEXT, hits INTEGER DEFAULT 0, created REAL)""")
    return con


def mint(artifacts: dict) -> str:
    token = secrets.token_urlsafe(8)
    con = _db()
    con.execute("INSERT INTO links(token, artifacts, created) VALUES(?,?,?)",
                (token, json.dumps(artifacts), time.time()))
    con.commit()
    con.close()
    return token


def resolve(token: str):
    con = _db()
    row = con.execute("SELECT artifacts FROM links WHERE token=?", (token,)).fetchone()
    if not row:
        con.close()
        return None
    con.execute("UPDATE links SET hits = hits + 1 WHERE token=?", (token,))
    con.commit()
    con.close()
    return json.loads(row[0])


def pick(artifacts: dict, user_agent: str) -> str | None:
    ua = (user_agent or "").lower()
    for needles, kind in UA_RULES:
        if any(n in ua for n in needles) and artifacts.get(kind):
            return artifacts[kind]
    return artifacts.get("pdf") or artifacts.get("apk") or artifacts.get("photo")


def hits(token: str) -> dict:
    con = _db()
    row = con.execute("SELECT hits, created FROM links WHERE token=?", (token,)).fetchone()
    con.close()
    if not row:
        return {"hits": 0}
    return {"hits": row[0], "created": row[1]}


def routes(app, ok, fail):  # noqa: A001
    from flask import request, redirect

    @app.post("/api/delivery/link")
    def delivery_link():
        body = request.get_json(silent=True) or {}
        artifacts = body.get("artifacts") or {}
        if not artifacts:
            return fail("artifacts required")
        token = mint(artifacts)
        base = request.host_url.rstrip("/")
        return ok({"token": token, "url": f"{base}/l/{token}"})

    @app.get("/l/<token>")
    def landing_redirect(token: str):
        arts = resolve(token)
        if arts is None:
            return fail("unknown link", 404)
        target = pick(arts, request.headers.get("User-Agent", ""))
        if not target:
            return fail("no artifact for this client", 406)
        return redirect(target, code=302)

    @app.get("/api/delivery/link/<token>/hits")
    def delivery_link_hits(token: str):
        return ok(hits(token))
