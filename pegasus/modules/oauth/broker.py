"""OAuth2+PKCE. Telegram HMAC. Signal URI relay."""
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import sqlite3
import subprocess
import time

import requests

from pegasus.core.config import public_url

DB = pathlib.Path.home() / ".pegasus" / "oauth.db"
PROVIDERS = {
    "discord": {"authorize": "https://discord.com/oauth2/authorize",
                "token": "https://discord.com/api/oauth2/token",
                "scope": "identify guilds", "env": "DISCORD"},
    "messenger": {"authorize": "https://www.facebook.com/v19.0/dialog/oauth",
                  "token": "https://graph.facebook.com/v19.0/oauth/access_token",
                  "scope": "pages_messaging", "env": "MESSENGER"},
    "whatsapp": {"authorize": "https://www.facebook.com/v19.0/dialog/oauth",
                 "token": "https://graph.facebook.com/v19.0/oauth/access_token",
                 "scope": "whatsapp_business_messaging", "env": "WHATSAPP"}}


def _db() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS tokens(provider TEXT PRIMARY KEY,"
                " access TEXT, refresh TEXT, expires REAL, extra TEXT)")
    return con


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def begin(provider: str, redirect_uri: str) -> dict:
    meta = PROVIDERS[provider]
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce()
    params = {"client_id": os.environ[f"{meta['env']}_CLIENT_ID"],
              "redirect_uri": redirect_uri, "response_type": "code",
              "scope": meta["scope"], "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256"}
    con = _db()
    con.execute("INSERT OR REPLACE INTO tokens(provider, extra) VALUES(?,?)",
                (f"pending:{provider}",
                 json.dumps({"state": state, "verifier": verifier,
                             "redirect": redirect_uri})))
    con.commit()
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return {"url": f"{meta['authorize']}?{query}", "state": state}


def complete(provider: str, code: str, state: str) -> dict:
    con = _db()
    row = con.execute("SELECT extra FROM tokens WHERE provider=?",
                      (f"pending:{provider}",)).fetchone()
    if not row:
        raise RuntimeError("no pending flow")
    pending = json.loads(row[0])
    if not hmac.compare_digest(state, pending["state"]):
        raise RuntimeError("state mismatch")
    meta = PROVIDERS[provider]
    data = {"client_id": os.environ[f"{meta['env']}_CLIENT_ID"],
            "client_secret": os.environ.get(f"{meta['env']}_CLIENT_SECRET", ""),
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": pending["redirect"],
            "code_verifier": pending["verifier"]}
    r = requests.post(meta["token"], data=data, timeout=30)
    r.raise_for_status()
    tok = r.json()
    con.execute("INSERT OR REPLACE INTO tokens(provider, access, refresh, expires)"
                " VALUES(?,?,?,?)",
                (provider, tok.get("access_token"), tok.get("refresh_token"),
                 time.time() + tok.get("expires_in", 3600)))
    con.commit()
    os.chmod(DB, 0o600)
    return {"provider": provider, "linked": True}


def token(provider: str) -> str | None:
    row = _db().execute("SELECT access, expires FROM tokens WHERE provider=?",
                        (provider,)).fetchone()
    if not row or not row[0] or (row[1] and row[1] < time.time()):
        return None
    return row[0]


def telegram_verify(payload: dict) -> bool:
    data = dict(payload)
    received = data.pop("hash", "")
    joined = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(os.environ["TELEGRAM_BOT_TOKEN"].encode()).digest()
    expect = hmac.new(secret, joined.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, received)


def relay_signal(uri: str) -> dict:
    proc = subprocess.run(["adb", "shell", "am", "start", "-a",
                           "android.intent.action.VIEW", "-d", uri],
                          capture_output=True, text=True, timeout=30)
    return {"code": proc.returncode, "out": proc.stdout.strip()[:200]}


def callback_base() -> str:
    return f"{public_url()}/api/oauth/callback"
