"""Metasploit RPC status routes.

Reports the RPC daemon on the configured host/port as **online** only when it
is genuinely reachable *and* the configured credentials authenticate - a bare
TCP probe is not enough, because msfrpcd answers on the socket long before a
client can talk to it.

Also exposes a start route that launches msfrpcd with the *configured*
password (the launcher used to hardcode a different one, which made a running
daemon fail every login).
"""
from __future__ import annotations

import base64
import json
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from flask import request


def _settings():
    from pegasus.core.config import get_settings

    return get_settings().metasploit


def _tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _rpc_login(host: str, port: int, password: str, timeout: float = 4.0) -> Dict[str, Any]:
    """Attempt an msfrpcd HTTP-RPC login. Never raises."""
    url = f"http://{host}:{port}/login"
    body = json.dumps({"username": "msf", "password": password}).encode()
    token = base64.b64encode(f"msf:{password}".encode()).decode()
    last_error = ""
    for headers in (
        {"Content-Type": "application/json", "Authorization": f"Basic {token}"},
        {"Content-Type": "application/json"},
    ):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {}
                if parsed.get("success") or parsed.get("token"):
                    return {"ok": True, "token": bool(parsed.get("token")), "error": ""}
                last_error = raw[:160]
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:120]}"
        except Exception as exc:  # noqa: BLE001 - connectivity issues are the answer
            last_error = f"{type(exc).__name__}: {exc}"
    return {"ok": False, "token": False, "error": last_error}


def _status() -> Dict[str, Any]:
    cfg = _settings()
    host = cfg.rpc_host or "127.0.0.1"
    port = int(cfg.rpc_port or 55553)
    configured = bool(host and port and cfg.rpc_password)
    out: Dict[str, Any] = {
        "host": host,
        "port": port,
        "configured": configured,
        "connected": False,
        "detail": "",
        "passwordSet": bool(cfg.rpc_password),
        "autoStart": bool(cfg.auto_start),
    }
    if not configured:
        out["detail"] = "metasploit rpc host/port/password not configured"
        return out
    if not _tcp_open(host, port):
        out["detail"] = f"nothing listening on {host}:{port}"
        return out
    login = _rpc_login(host, port, cfg.rpc_password)
    out["connected"] = bool(login["ok"])
    out["detail"] = "rpc login accepted" if login["ok"] else f"rpc login failed: {login['error']}"
    return out


def register(app, ok, fail):
    @app.get("/api/metasploit/status")
    def metasploit_status():
        return ok(_status())

    @app.post("/api/metasploit/start")
    def metasploit_start():
        from pegasus.core import services

        result = services.start_msfrpcd()
        return ok({"service": result, "status": _status()})
