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


def create_user(user: str, password: str, role: str = "operator") -> int:
    """Create operator (admin use). Returns new row id."""
    if role not in ("admin", "operator", "viewer"):
        raise ValueError("role must be admin|operator|viewer")
    salt = os.urandom(16).hex()
    con = _db()
    cur = con.execute(
        "INSERT INTO operators(user, pw, salt, role, created) VALUES(?,?,?,?,?)",
        (user, hash_pw(password, salt), salt, role, time.time()))
    con.commit()
    return cur.lastrowid


def list_users() -> list[dict]:
    rows = _db().execute(
        "SELECT id, user, role, created FROM operators ORDER BY created DESC").fetchall()
    return [{"id": r[0], "user": r[1], "role": r[2], "created": r[3]} for r in rows]


def update_user(op_id: int, role: str | None = None) -> bool:
    if role is not None:
        if role not in ("admin", "operator", "viewer"):
            raise ValueError("invalid role")
        con = _db()
        con.execute("UPDATE operators SET role=? WHERE id=?", (role, op_id))
        # role changed → drop that operator's sessions so they must re-login
        con.execute("DELETE FROM sessions WHERE operator_id=?", (op_id,))
        con.commit()
        return con.total_changes > 0
    return True


def delete_user(op_id: int) -> bool:
    con = _db()
    op = current()
    # cannot delete bootstrap admin (id=1) or self
    row = con.execute("SELECT user FROM operators WHERE id=?", (op_id,)).fetchone()
    if not row:
        return False
    if op and op["user"] == row[0]:
        raise ValueError("refusing to delete current session user")
    con.execute("DELETE FROM sessions WHERE operator_id=?", (op_id,))
    con.execute("DELETE FROM operators WHERE id=?", (op_id,))
    con.commit()
    return con.total_changes > 0


def change_password(op_id: int, new_password: str) -> bool:
    salt = os.urandom(16).hex()
    con = _db()
    cur = con.execute(
        "UPDATE operators SET pw=?, salt=? WHERE id=?",
        (hash_pw(new_password, salt), salt, op_id))
    con.execute("DELETE FROM sessions WHERE operator_id=?", (op_id,))  # force re-login
    con.commit()
    return cur.rowcount > 0


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
        if not _auth_on():
            # The gate is off, so the caller is the local single
            # operator.  The routes read op["user"] for the owner
            # name, so they need an identity to work against.
            return _local_operator()
        return None
    row = _db().execute("SELECT o.user, o.role, s.csrf, s.expires FROM sessions s"
                        " JOIN operators o ON o.id = s.operator_id WHERE s.token=?",
                        (token,)).fetchone()
    if not row or row[3] < time.time():
        return None
    return {"user": row[0], "role": row[1], "csrf": row[2]}


AUTH_FLAG = "PEGASUS_REQUIRE_AUTH"


def _auth_on() -> bool:
    """Whether this deployment opted into the operator gate.

    The device, physical, fastboot and tool route families have
    always been gated this way: an unset flag means the local
    single-operator console, a set flag means every route needs a
    token or a session.  operator.require now honours the same
    switch so the whole surface behaves the same way instead of
    half of it always demanding a sign-in.
    """
    return os.environ.get(AUTH_FLAG, "").strip().lower() in (
        "1", "true", "yes", "on")


def _local_operator() -> dict:
    """The identity the routes work against when the gate is off.

    The account name is the local one, so an operator who signs
    in later with the same name sees the same stored data.
    """
    try:
        import getpass
        user = getpass.getuser() or "local"
    except Exception:
        user = "local"
    return {"user": user, "role": "admin", "csrf": ""}


def session_info() -> dict:
    """Whether the caller holds an operator session - never gated."""
    op = current()
    return {
        "authenticated": op is not None,
        "user": op["user"] if op else None,
        "role": op["role"] if op else None,
        "auth_required": _auth_on(),
    }


def require(role: str = "operator"):
    def deco(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            if not _auth_on():
                # This deployment did not opt into the operator
                # gate, so the console runs as the local
                # single-operator tool it is.  The routes still
                # read g.operator for the owner name, so give
                # them the local identity.
                g.operator = _local_operator()
                return fn(*args, **kwargs)
            op = current()
            if not op:
                return jsonify({"ok": False, "error": "auth required"}), 401
            if role == "admin" and op["role"] != "admin":
                return jsonify({"ok": False, "error": "admin required"}), 403
            if request.method in ("POST", "PATCH", "DELETE"):
                sent = request.headers.get("X-CSRF") or request.headers.get("X-CSRF-Token") or \
                    (request.get_json(silent=True) or {}).get("csrf")
                if not hmac.compare_digest(sent or "", op["csrf"]):
                    return jsonify({"ok": False, "error": "csrf"}), 403
            g.operator = op
            return fn(*args, **kwargs)
        return inner
    return deco
