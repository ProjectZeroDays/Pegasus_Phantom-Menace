"""Session auth plus CSRF."""
import functools
import hashlib
import hmac
import os
import pathlib
import secrets
import sqlite3
import time

from flask import g, jsonify, request, session

DB = pathlib.Path.home() / ".pegasus" / "operators.db"


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS operators(id INTEGER PRIMARY KEY,"
                " user TEXT UNIQUE, pw TEXT, salt TEXT, role TEXT, created REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,"
                " operator_id INTEGER, csrf TEXT, expires REAL)")
    return con


def hash_pw(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14,
                          r=8, p=1).hex()


def bootstrap(user: str, password: str) -> None:
    con = _db()
    if con.execute("SELECT 1 FROM operators LIMIT 1").fetchone():
        return
    salt = os.urandom(16).hex()
    con.execute("INSERT INTO operators(user, pw, salt, role, created)"
                " VALUES(?,?,?,?,?)",
                (user, hash_pw(password, salt), salt, "admin", time.time()))
    con.commit()


def login(user: str, password: str) -> str | None:
    row = _db().execute("SELECT id, pw, salt FROM operators WHERE user=?",
                        (user,)).fetchone()
    if not row or not hmac.compare_digest(hash_pw(password, row[2]), row[1]):
        return None
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    con = _db()
    con.execute("INSERT INTO sessions VALUES(?,?,?,?)",
                (token, row[0], csrf, time.time() + 86400))
    con.commit()
    session["op"] = token
    return csrf


def current() -> dict | None:
    token = session.get("op")
    if not token:
        return None
    row = _db().execute("SELECT o.user, o.role, s.csrf, s.expires FROM sessions s"
                        " JOIN operators o ON o.id = s.operator_id WHERE s.token=?",
                        (token,)).fetchone()
    if not row or row[3] < time.time():
        return None
    return {"user": row[0], "role": row[1], "csrf": row[2]}


def require(role: str = "operator"):
    def deco(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            op = current()
            if not op:
                return jsonify({"ok": False, "error": "auth required"}), 401
            if role == "admin" and op["role"] != "admin":
                return jsonify({"ok": False, "error": "admin required"}), 403
            if request.method in ("POST", "PATCH", "DELETE"):
                sent = request.headers.get("X-CSRF") or \
                    (request.get_json(silent=True) or {}).get("csrf")
                if not hmac.compare_digest(sent or "", op["csrf"]):
                    return jsonify({"ok": False, "error": "csrf"}), 403
            g.operator = op
            return fn(*args, **kwargs)
        return inner
    return deco
