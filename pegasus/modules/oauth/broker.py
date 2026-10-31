#!/usr/bin/env python3
"""OAuth broker — PKCE flows for Discord / Messenger / WhatsApp, Telegram hash-verify, Signal QR relay."""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import pathlib
import secrets
import sqlite3
import time

DB = pathlib.Path.home() / ".pegasus" / "oauth.db"

PROVIDERS = {
    "discord": {
        "authorize": "https://discord.com/oauth2/authorize",
        "token": "https://discord.com/api/oauth2/token",
        "scope": "identify guilds", "pkce": True,
    },
    "messenger": {
        "authorize": "https://www.facebook.com/v19.0/dialog/oauth",
        "token": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scope": "pages_messaging", "pkce": True,
    },
    "whatsapp": {
        "authorize": "https://www.facebook.com/v19.0/dialog/oauth",
        "token": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scope": "whatsapp_business_messaging", "pkce": True,
    },
}


def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS tokens(
        provider TEXT PRIMARY KEY, access TEXT, refresh TEXT, expires REAL, extra TEXT)""")
    return con


def _pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def begin(provider: str, redirect: str) -> dict:
    if provider not in PROVIDERS:
        raise RuntimeError(f"unknown provider {provider}")
    meta = PROVIDERS[provider]
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": os.environ[f"{provider.upper()}_CLIENT_ID"],
        "redirect_uri": redirect, "response_type": "code",
        "scope": meta["scope"], "state": state,
    }
    verifier = None
    if meta["pkce"]:
        verifier, challenge = _pkce()
        params.update(code_challenge=challenge, code_challenge_method="S256")
    con = _db()
    con.execute("INSERT OR REPLACE INTO tokens(provider, extra) VALUES(?,?)",
                (f"pending:{provider}", f"{state}|{verifier}|{redirect}"))
    con.commit()
    con.close()
    import requests
    q = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return {"url": f"{meta['authorize']}?{q}", "state": state}


def complete(provider: str, code: str, state: str) -> dict:
    if provider not in PROVIDERS:
        raise RuntimeError(f"unknown provider {provider}")
    con = _db()
    row = con.execute("SELECT extra FROM tokens WHERE provider=?", (f"pending:{provider}",)).fetchone()
    if not row:
        con.close()
        raise RuntimeError("no pending flow")
    want_state, verifier, redirect = row[0].split("|")
    if state != want_state:
        con.close()
        raise RuntimeError("state mismatch")
    meta = PROVIDERS[provider]
    data = {
        "client_id": os.environ[f"{provider.upper()}_CLIENT_ID"],
        "client_secret": os.environ.get(f"{provider.upper()}_CLIENT_SECRET", ""),
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
    }
    if verifier and verifier != "None":
        data["code_verifier"] = verifier
    import requests
    r = requests.post(meta["token"], data=data, timeout=30)
    r.raise_for_status()
    tok = r.json()
    con.execute("INSERT OR REPLACE INTO tokens(provider, access, refresh, expires) VALUES(?,?,?,?)",
                (provider, tok.get("access_token"), tok.get("refresh_token"),
                 time.time() + tok.get("expires_in", 3600)))
    con.commit()
    con.close()
    return {"provider": provider, "ok": True}


def telegram_verify(data: dict) -> bool:
    """Telegram Login Widget: signed hash, verified with the bot token."""
    data = dict(data)
    check = data.pop("hash", "")
    joined = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(os.environ["TELEGRAM_BOT_TOKEN"].encode()).digest()
    return hmac.compare_digest(
        hmac.new(secret, joined.encode(), hashlib.sha256).hexdigest(), check)


def signal_relay(uri: str) -> dict:
    """Forward sgnl:// link to a connected Android device via adb."""
    import subprocess
    proc = subprocess.run(["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", uri],
                          capture_output=True, text=True, timeout=20)
    return {"ok": proc.returncode == 0, "output": proc.stdout[-500:]}


def routes(app, ok, fail):  # noqa: A001
    from flask import request, redirect as flask_redirect

    @app.get("/api/oauth/login/<provider>")
    def oauth_login(provider: str):
        redirect_uri = f"{request.host_url.rstrip('/')}/api/oauth/callback/{provider}"
        try:
            out = begin(provider, redirect_uri)
        except (RuntimeError, KeyError) as exc:
            return fail(str(exc), 400)
        return flask_redirect(out["url"], code=302)

    @app.get("/api/oauth/callback/<provider>")
    def oauth_callback(provider: str):
        code = request.args.get("code", "")
        state = request.args.get("state", "")
        if not code:
            return fail("missing code", 400)
        try:
            result = complete(provider, code, state)
        except RuntimeError as exc:
            return fail(str(exc), 400)
        return flask_redirect(f"/settings?linked={provider}", code=302)

    @app.post("/api/oauth/telegram")
    def oauth_telegram():
        body = request.get_json(silent=True) or {}
        if not telegram_verify(body):
            return fail("hash mismatch", 401)
        return ok({"provider": "telegram", "ok": True, "user": body.get("username")})

    @app.post("/api/oauth/signal/link")
    def oauth_signal():
        body = request.get_json(silent=True) or {}
        uri = body.get("uri") or ""
        if not uri.startswith("sgnl://"):
            return fail("uri must be sgnl://")
        return ok(signal_relay(uri))
