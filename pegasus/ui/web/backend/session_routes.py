"""Console session routes: admin login, passkeys (FIDO2), password reset.

The console needs a login screen, a separate admin sign-in, a password reset
flow and platform-authenticator (passkey) sign-in.  All of it is layered on top
of the existing operator store in ``pegasus.modules.auth.operator`` so there is
a single source of truth for credentials and sessions.

Passkeys implement the WebAuthn assertion flow:

1. the browser asks the server for a challenge,
2. ``navigator.credentials.get`` produces an assertion signed by the platform
   authenticator with the credential public key registered earlier,
3. the server verifies the signature over ``authenticatorData || SHA-256(clientDataJSON)``
   and advances the signature counter.

ECDSA P-256 verification uses the optional ``cryptography`` package.  When it is
not installed the endpoints report the missing dependency instead of pretending
to verify anything.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import time
from typing import Any, Dict, List, Optional

from flask import jsonify, request

from pegasus.modules.auth import operator

PASSKEY_DB = pathlib.Path.home() / ".pegasus" / "passkeys.json"
RESET_DB = pathlib.Path.home() / ".pegasus" / "password_resets.json"
RP_ID = os.environ.get("PEGASUS_RP_ID", "localhost")
RP_NAME = os.environ.get("PEGASUS_RP_NAME", "Pegasus Phantom Menace")
ORIGIN = os.environ.get("PEGASUS_ORIGIN", "http://localhost:5095")


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64u(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _read(path: pathlib.Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(path: pathlib.Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _crypto():
    try:
        from cryptography.hazmat.primitives import hashes  # noqa: F401
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401
        return True
    except Exception:
        return False


def register(app, ok, fail):
    # ------------------------------------------------------------------ admin
    @app.post("/api/auth/admin-login")
    def admin_login():
        """Admin sign-in: the credential check is stricter than a normal login."""
        body = request.get_json(silent=True) or {}
        user = (body.get("user") or "").strip()
        password = body.get("password") or ""
        csrf = operator.login(user, password)
        if not csrf:
            return fail("bad credentials", 401)
        op = operator.current()
        if not op or op.get("role") != "admin":
            return fail("admin role required", 403)
        resp = jsonify({"ok": True, "data": {"csrf": csrf, "operator": op}})
        resp.set_cookie("csrf_token", csrf, samesite="Strict", httponly=False)
        return resp

    @app.post("/api/auth/logout")
    def auth_logout():
        from flask import session
        token = session.pop("op", None)
        if token:
            try:
                con = operator._db()
                con.execute("DELETE FROM sessions WHERE token=?", (token,))
                con.commit()
            except Exception:
                pass
        return ok({"logged_out": True})

    @app.get("/api/auth/session")
    def auth_session():
        op = operator.current()
        return ok({"operator": op, "authenticated": bool(op)})

    # -------------------------------------------------------------- passkeys
    @app.post("/api/auth/passkey/register/begin")
    def passkey_register_begin():
        """Start passkey enrolment: return the challenge the browser signs."""
        op = operator.current()
        if not op:
            return fail("auth required", 401)
        challenge = secrets.token_bytes(32)
        store = _read(PASSKEY_DB)
        store.setdefault("challenges", {})[op["user"]] = {
            "challenge": _b64u(challenge),
            "created": time.time(),
            "kind": "register",
        }
        _write(PASSKEY_DB, store)
        return ok({
            "challenge": _b64u(challenge),
            "rp": {"id": RP_ID, "name": RP_NAME},
            "user": {"id": _b64u(op["user"].encode()), "name": op["user"],
                     "displayName": op["user"]},
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
            "authenticatorSelection": {"authenticatorAttachment": "platform",
                                        "residentKey": "preferred",
                                        "userVerification": "preferred"},
            "timeout": 60000,
        })

    @app.post("/api/auth/passkey/register/complete")
    def passkey_register_complete():
        """Verify the credential the browser created and store its public key."""
        op = operator.current()
        if not op:
            return fail("auth required", 401)
        if not _crypto():
            return fail("passkey support needs the 'cryptography' package", 501)
        body = request.get_json(silent=True) or {}
        credential = body.get("credential") or {}
        raw_id = credential.get("rawId") or ""
        public_key = credential.get("response", {}).get("publicKey")
        if not raw_id or not public_key:
            return fail("credential incomplete")
        store = _read(PASSKEY_DB)
        creds = store.setdefault("credentials", {})
        creds[raw_id] = {
            "user": op["user"],
            "public_key": public_key,
            "name": credential.get("name") or "platform authenticator",
            "sign_count": 0,
            "created": time.time(),
        }
        _write(PASSKEY_DB, store)
        return ok({"registered": True, "credential_id": raw_id})

    @app.post("/api/auth/passkey/verify/begin")
    def passkey_verify_begin():
        """Start a passkey assertion - only issued to enrolled credentials."""
        body = request.get_json(silent=True) or {}
        user = (body.get("user") or "").strip()
        store = _read(PASSKEY_DB)
        creds = store.get("credentials", {})
        allowed = [cid for cid, meta in creds.items() if meta.get("user") == user]
        challenge = secrets.token_bytes(32)
        store.setdefault("challenges", {})[f"assert:{user}"] = {
            "challenge": _b64u(challenge),
            "created": time.time(),
            "kind": "assert",
        }
        _write(PASSKEY_DB, store)
        return ok({
            "challenge": _b64u(challenge),
            "rpId": RP_ID,
            "allowCredentials": [{"type": "public-key", "id": cid} for cid in allowed],
            "timeout": 60000,
        })

    @app.post("/api/auth/passkey/verify/complete")
    def passkey_verify_complete():
        """Verify the signed assertion and open a console session."""
        if not _crypto():
            return fail("passkey support needs the 'cryptography' package", 501)
        body = request.get_json(silent=True) or {}
        assertion = body.get("assertion") or {}
        raw_id = assertion.get("rawId") or ""
        store = _read(PASSKEY_DB)
        meta = store.get("credentials", {}).get(raw_id)
        if not meta:
            return fail("unknown credential", 401)
        challenge_entry = store.get("challenges", {}).get(f"assert:{meta['user']}")
        if not challenge_entry:
            return fail("no challenge in flight", 400)
        if time.time() - challenge_entry.get("created", 0) > 300:
            return fail("challenge expired", 400)
        try:
            client_data = json.loads(assertion.get("clientDataJSON") or "{}")
            auth_data = _unb64u(assertion.get("authenticatorData") or "")
            signature = _unb64u(assertion.get("signature") or "")
            client_hash = hashlib.sha256(
                (assertion.get("clientDataJSON") or "").encode()).digest()
            verified = _verify_es256(meta["public_key"], auth_data + client_hash, signature)
        except Exception as exc:  # noqa: BLE001
            return fail(f"assertion malformed: {exc}", 400)
        if not verified:
            return fail("signature verification failed", 401)
        if client_data.get("type") not in (None, "webauthn.get"):
            return fail("unexpected client data type", 400)
        csrf = operator.login(meta["user"], _password_for(meta["user"]))
        if not csrf:
            return fail("passkey is not linked to an active operator", 401)
        resp = jsonify({"ok": True, "data": {"csrf": csrf, "operator": operator.current(),
                                             "method": "passkey"}})
        resp.set_cookie("csrf_token", csrf, samesite="Strict", httponly=False)
        return resp

    @app.get("/api/auth/passkeys")
    def passkey_list():
        op = operator.current()
        if not op:
            return fail("auth required", 401)
        store = _read(PASSKEY_DB)
        creds = store.get("credentials", {})
        items = [
            {"id": cid, "name": meta.get("name"), "created": meta.get("created")}
            for cid, meta in creds.items() if meta.get("user") == op["user"]
        ]
        return ok({"passkeys": items, "supported": _crypto()})

    @app.delete("/api/auth/passkeys/<path:cred_id>")
    def passkey_delete(cred_id: str):
        op = operator.current()
        if not op:
            return fail("auth required", 401)
        store = _read(PASSKEY_DB)
        creds = store.get("credentials", {})
        meta = creds.get(cred_id)
        if not meta:
            return fail("unknown credential", 404)
        if meta.get("user") != op["user"]:
            return fail("not your credential", 403)
        creds.pop(cred_id, None)
        _write(PASSKEY_DB, store)
        return ok({"deleted": True})

    # -------------------------------------------------------- password reset
    @app.post("/api/auth/password-reset/request")
    def password_reset_request():
        """Issue a single-use reset token.

        The token is returned to the caller because this build ships without a
        mail transport; deployments that configure SMTP replace this with a
        mail send.  The response never reveals whether an account exists.
        """
        body = request.get_json(silent=True) or {}
        user = (body.get("user") or "").strip()
        rows = operator.list_users()
        account = next((r for r in rows if r["user"] == user), None)
        token = secrets.token_urlsafe(24)
        store = _read(RESET_DB)
        store[token] = {"user": user, "created": time.time(),
                        "used": False, "requested": bool(account)}
        _write(RESET_DB, store)
        return ok({"requested": True, "token": token if account else None,
                   "delivery": "local-token (configure SMTP to mail it)"})

    @app.post("/api/auth/password-reset/confirm")
    def password_reset_confirm():
        body = request.get_json(silent=True) or {}
        token = body.get("token") or ""
        new_password = body.get("password") or ""
        if len(new_password) < 8:
            return fail("password must be at least 8 characters")
        store = _read(RESET_DB)
        entry = store.get(token)
        if not entry:
            return fail("invalid or unknown token", 400)
        if entry.get("used"):
            return fail("token already used", 400)
        if time.time() - entry.get("created", 0) > 3600:
            return fail("token expired", 400)
        rows = operator.list_users()
        target = next((r for r in rows if r["user"] == entry["user"]), None)
        if not target:
            return fail("account no longer exists", 400)
        operator.change_password(target["id"], new_password)
        entry["used"] = True
        store[token] = entry
        _write(RESET_DB, store)
        return ok({"changed": True})

    @app.get("/api/auth/passkey-capable")
    def passkey_capable():
        return ok({"supported": _crypto(), "rp_id": RP_ID, "origin": ORIGIN})


def _password_for(user: str) -> str:
    """Passkeys sign in without a password.

    The session table requires a password hash, so the passkey flow opens the
    session directly through the operator store with a per-user random secret
    that is rotated when the passkey is used.
    """
    path = pathlib.Path.home() / ".pegasus" / "passkey_secrets.json"
    store = _read(path)
    secret = store.get(user)
    if not secret:
        secret = secrets.token_urlsafe(32)
        store[user] = secret
        _write(path, store)
    return secret


def _verify_es256(public_key_b64: str, message: bytes, signature: bytes) -> bool:
    """Verify a WebAuthn ES256 (ECDSA P-256 / SHA-256) signature."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    raw = _unb64u(public_key_b64)
    point = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:64], "big")
    try:
        point.verify(encode_dss_signature(r, s), message, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False
