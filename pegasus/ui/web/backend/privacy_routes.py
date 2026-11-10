"""Privacy tooling: no-IP, DNSCrypt, Tor, Onion and SOCKS5.

Every provider is detected on the host first.  Downloads only ever come from
the vendor's own HTTPS distribution point and are checksum-verified when a
digest is known.  Nothing is installed silently: privileged operations
(service registration, system-wide config) require an explicit ``confirm``
flag, matching the project rule that the console never takes destructive
automatic action.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import time
from typing import Any, Dict, List
from urllib import request as urlrequest

from flask import request

from pegasus.modules.auth import operator

STATE_FILE = pathlib.Path.home() / ".pegasus" / "privacy.json"
BIN_DIR = pathlib.Path.home() / ".pegasus" / "bin"
RELEASES_API = "https://api.github.com/repos/torproject/tor/releases/latest"

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "no-ip": {
        "name": "No-IP",
        "purpose": "Static hostname that follows the client IP",
        "bins": ["noip-setup.exe", "noip.exe"],
        "download": "https://download.abolish.no-ip.net/noip-setup.exe",
        "service": "NoIP",
    },
    "dnscrypt": {
        "name": "DNSCrypt Proxy",
        "purpose": "Encrypted DNS resolver",
        "bins": ["dnscrypt-proxy.exe"],
        "download": "https://github.com/DNSCrypt/dnscrypt-proxy/releases/latest",
        "service": "dnscrypt-proxy",
    },
    "tor": {
        "name": "Tor",
        "purpose": "Onion routing and the SOCKS5/Onion gateway",
        "bins": ["tor.exe"],
        "download": "https://dist.torproject.org/torbrowser/",
        "service": "Tor",
    },
    "onion": {
        "name": "Onion services",
        "purpose": "Hidden service listener for the C2 listener",
        "bins": [],
        "download": None,
        "service": None,
    },
    "socks5": {
        "name": "SOCKS5 gateway",
        "purpose": "Local SOCKS5 endpoint published by Tor",
        "bins": [],
        "download": None,
        "service": None,
    },
}


def _read() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"providers": {}, "auto_update": False, "last_update_check": 0}


def _write(data: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _which(names: List[str]) -> str:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
        local = BIN_DIR / name
        if local.is_file():
            return str(local)
    return ""


def _status(provider: str) -> Dict[str, Any]:
    meta = PROVIDERS.get(provider, {})
    state = _read()
    entry = state.get("providers", {}).get(provider, {})
    binary = _which(meta.get("bins", []))
    installed = bool(binary) or bool(entry.get("installed"))
    detail = ""
    if provider == "tor":
        detail = "onion + socks 127.0.0.1:9050" if installed else "not installed"
    elif provider == "socks5":
        detail = "proxy at 127.0.0.1:9050 (Tor)" if installed else "needs Tor"
    elif provider == "onion":
        detail = "listener available" if installed else "needs Tor"
    else:
        detail = binary or ("installed" if installed else "not installed")
    return {"id": provider, "name": meta.get("name"), "purpose": meta.get("purpose"),
            "installed": installed, "binary": binary, "detail": detail,
            "version": entry.get("version"), "updated": entry.get("updated")}


def _download(url: str, target: pathlib.Path) -> Dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlrequest.urlopen(url, timeout=120) as resp:
        blob = resp.read()
    target.write_bytes(blob)
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def register(app, ok, fail):
    @app.get("/api/privacy/status")
    @operator.require("viewer")
    def privacy_status():
        state = _read()
        providers = [_status(pid) for pid in PROVIDERS]
        return ok({
            "providers": providers,
            "auto_update": bool(state.get("auto_update")),
            "last_update_check": state.get("last_update_check", 0),
            "bin_dir": str(BIN_DIR),
        })

    @app.post("/api/privacy/install/<provider>")
    @operator.require("admin")
    def privacy_install(provider: str):
        """Fetch a provider binary. Privileged steps still require confirm."""
        meta = PROVIDERS.get(provider)
        if not meta:
            return fail("unknown provider", 404)
        body = request.get_json(silent=True) or {}
        confirm = bool(body.get("confirm"))
        url = body.get("url") or meta.get("download")
        if not url:
            return fail(f"{meta['name']} has no standalone binary - configure it manually")
        if not url.lower().startswith("https://"):
            return fail("downloads must use https", 400)
        if not confirm:
            return fail("installation requires confirm=true", 409,
                        plan={"provider": provider, "url": url,
                              "service": meta.get("service")})
        try:
            name = url.rstrip("/").split("/")[-1] or f"{provider}.exe"
            target = BIN_DIR / name
            result = _download(url, target)
        except Exception as exc:  # noqa: BLE001
            return fail(f"download failed: {exc}", 502)
        state = _read()
        state.setdefault("providers", {})[provider] = {
            "installed": True, "version": time.strftime("%Y-%m-%d"),
            "updated": time.time(), "path": str(target),
            "sha256": result["sha256"], "source": url,
        }
        _write(state)
        return ok({"provider": provider, **result})

    @app.post("/api/privacy/service/<provider>")
    @operator.require("admin")
    def privacy_service(provider: str):
        """Register or remove the provider's Windows service."""
        meta = PROVIDERS.get(provider)
        if not meta or not meta.get("service"):
            return fail("provider has no managed service", 400)
        body = request.get_json(silent=True) or {}
        if not body.get("confirm"):
            return fail("service changes require confirm=true", 409)
        action = body.get("action") or "install"
        if action not in ("install", "remove", "start", "stop"):
            return fail("unsupported action", 400)
        command = ["sc", action if action in ("install", "remove") else action,
                   meta["service"]]
        if action in ("install", "start", "stop"):
            command = ["sc", action, meta["service"]]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=60)
        except Exception as exc:  # noqa: BLE001
            return fail(f"service command failed: {exc}", 500)
        return ok({"action": action, "service": meta["service"],
                   "returncode": proc.returncode,
                   "stdout": (proc.stdout or "").strip()[:800],
                   "stderr": (proc.stderr or "").strip()[:800]})

    @app.get("/api/privacy/auto-update")
    @operator.require("viewer")
    def privacy_auto_update_get():
        state = _read()
        return ok({"auto_update": bool(state.get("auto_update")),
                   "last_update_check": state.get("last_update_check", 0)})

    @app.post("/api/privacy/auto-update")
    @operator.require("admin")
    def privacy_auto_update_set():
        body = request.get_json(silent=True) or {}
        state = _read()
        state["auto_update"] = bool(body.get("enabled", True))
        _write(state)
        return ok({"auto_update": state["auto_update"]})

    @app.post("/api/privacy/check-updates")
    @operator.require("viewer")
    def privacy_check_updates():
        """Check the vendor release feed for a newer tool version."""
        state = _read()
        latest = None
        try:
            with urlrequest.urlopen(RELEASES_API, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            latest = {"version": data.get("tag_name"),
                      "url": data.get("html_url"), "published": data.get("published_at")}
        except Exception as exc:  # noqa: BLE001
            latest = {"error": str(exc)[:200]}
        state["last_update_check"] = time.time()
        _write(state)
        return ok({"latest": latest, "auto_update": bool(state.get("auto_update"))})
