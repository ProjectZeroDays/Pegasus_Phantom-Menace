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
import hashlib
import json
import os
import pathlib
import shutil
import socket
import subprocess
import time
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


def _rpc_login(host: str, port: int, password: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Attempt an msfrpcd login.

    msfrpcd speaks MSGRPC - MessagePack payloads behind a four byte length
    prefix on a raw socket - not HTTP.  Posting JSON made the daemon reset
    the connection, so a healthy daemon always looked offline.
    """
    try:
        from pegasus.core.msgrpc import login as msgrpc_login
        result = msgrpc_login(host, port, "msf", password, timeout)
        if result.get("ok"):
            return result
        last_error = str(result.get("error") or "login refused")
    except Exception as exc:  # noqa: BLE001 - connectivity issues are the answer
        last_error = f"{type(exc).__name__}: {exc}"

    # Older daemons answered a JSON login on the same socket.
    try:
        url = f"http://{host}:{port}/login"
        body = json.dumps({"username": "msf", "password": password}).encode()
        token = base64.b64encode(f"msf:{password}".encode()).decode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Basic {token}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            if parsed.get("success") or parsed.get("token"):
                return {"ok": True, "token": bool(parsed.get("token")), "error": ""}
    except Exception:
        pass
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


# ---------------------------------------------------------------------------
# installer - find, download and (optionally) install the Metasploit daemon
# ---------------------------------------------------------------------------

MSF_LATEST = "https://api.github.com/repos/rapid7/metasploit-framework/releases/latest"
TOOLS_DIR = pathlib.Path.home() / ".pegasus" / "tools"
MSF_DIR = TOOLS_DIR / "metasploit"
MSF_STATE = pathlib.Path.home() / ".pegasus" / "metasploit_install.json"
DOWNLOAD_TIMEOUT = 1800


def _candidate_binaries() -> list:
    """Every place a Metasploit install may live on this host."""
    found = []
    for name in ("msfrpcd.exe", "msfrpcd", "msfconsole.exe", "msfconsole"):
        which = shutil.which(name)
        if which:
            found.append(str(pathlib.Path(which).resolve()))
    bases = [
        MSF_DIR,
        pathlib.Path("C:/metasploit"),
        pathlib.Path.home() / "metasploit",
        pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) /
        "Programs" / "Metasploit",
    ]
    for base in bases:
        for rel in ("bin/msfrpcd.exe", "msfrpcd.exe", "bin/msfconsole.exe"):
            candidate = base / rel
            if candidate.is_file():
                found.append(str(candidate))
    seen, unique = set(), []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _detect_install() -> dict:
    binaries = _candidate_binaries()
    state = {}
    try:
        state = json.loads(MSF_STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    return {
        "installed": bool(binaries),
        "binaries": binaries,
        "msfrpcd": next((b for b in binaries if "msfrpcd" in b.lower()), ""),
        "msfconsole": next((b for b in binaries if "msfconsole" in b.lower()), ""),
        "install_dir": str(MSF_DIR),
        "downloaded": state.get("downloaded"),
        "version": state.get("version"),
        "sha256": state.get("sha256"),
    }


def _latest_release() -> dict:
    """The current Metasploit Framework release and its Windows installer."""
    req = urllib.request.Request(
        MSF_LATEST, headers={"User-Agent": "Pegasus/2.2", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    assets = data.get("assets") or []
    msi = next((a for a in assets if str(a.get("name", "")).lower().endswith(".msi")
                and "x64" in str(a.get("name", "")).lower()), None)
    if not msi:
        msi = next((a for a in assets if str(a.get("name", "")).lower().endswith(".msi")), None)
    return {
        "version": data.get("tag_name"),
        "url": data.get("html_url"),
        "asset": msi,
        "published": data.get("published_at"),
    }


def _download(url: str, target: pathlib.Path) -> dict:
    if not url.lower().startswith("https://"):
        raise ValueError("downloads must use https")
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Pegasus/2.2"}),
            timeout=DOWNLOAD_TIMEOUT) as resp, target.open("wb") as handle:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    return {"bytes": total, "sha256": digest.hexdigest(), "path": str(target)}


def register(app, ok, fail):
    @app.get("/api/metasploit/status")
    def metasploit_status():
        return ok(_status())

    @app.post("/api/metasploit/start")
    def metasploit_start():
        from pegasus.core import services

        result = services.start_msfrpcd()
        return ok({"service": result, "status": _status()})

    @app.get("/api/metasploit/autostart")
    def metasploit_autostart_status():
        """Whether the RPC daemon is registered to start at logon."""
        from pegasus.core import services

        return ok(services.msfrpcd_autostart_status())

    @app.post("/api/metasploit/autostart")
    def metasploit_autostart_set():
        """Register or remove the msfrpcd startup entry.

        Nothing is written without ``confirm`` - the console never takes a
        silent system-changing action.  The RPC password is resolved by the
        generated launcher at run time, so it never reaches the task
        definition.
        """
        body = request.get_json(silent=True) or {}
        if not body.get("confirm"):
            return fail("startup registration requires confirm=true", 409)
        from pegasus.core import services

        enabled = bool(body.get("enabled", True))
        result = services.msfrpcd_autostart(enabled)
        if enabled and not result.get("autostart"):
            return fail(result.get("detail") or "could not register the startup entry", 502)
        return ok(result)

    @app.get("/api/metasploit/install/status")
    def metasploit_install_status():
        return ok({"install": _detect_install(),
                   "tools_dir": str(TOOLS_DIR)})

    @app.post("/api/metasploit/install")
    def metasploit_install():
        """Download and optionally install the Metasploit RPC daemon.

        Nothing is written without ``confirm`` - the console never takes a
        silent system-changing action.
        """
        body = request.get_json(silent=True) or {}
        confirm = bool(body.get("confirm"))
        detection = _detect_install()
        try:
            release = _latest_release()
        except Exception as exc:  # noqa: BLE001
            return fail(f"cannot reach the release feed: {exc}", 502)
        asset = release.get("asset")
        if not asset:
            return fail("the current release publishes no Windows installer", 400)
        plan = {
            "version": release.get("version"),
            "asset": asset.get("name"),
            "size": asset.get("size"),
            "url": asset.get("browser_download_url"),
            "install_dir": str(MSF_DIR),
            "silent_install": f'msiexec /i "{asset.get("browser_download_url")}" /qn '
                              f'INSTALLDIR="{MSF_DIR}"',
            "note": "The installer is downloaded from the official Metasploit "
                    "release. Installation may need elevation.",
        }
        if not confirm:
            return ok({"needs_confirm": True, "plan": plan, "install": detection})
        try:
            target = TOOLS_DIR / str(asset.get("name"))
            if not target.is_file():
                result = _download(str(asset.get("browser_download_url")), target)
            else:
                result = {"bytes": target.stat().st_size, "sha256": "", "path": str(target)}
        except Exception as exc:  # noqa: BLE001
            return fail(f"download failed: {exc}", 502)
        state = {"downloaded": time.time(), "version": release.get("version"),
                 "path": str(target), "sha256": result.get("sha256")}
        try:
            MSF_STATE.parent.mkdir(parents=True, exist_ok=True)
            MSF_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass
        installed = False
        detail = "downloaded only"
        if body.get("install"):
            try:
                proc = subprocess.run(
                    ["msiexec", "/i", str(target), "/qn",
                     f"INSTALLDIR={MSF_DIR}"],
                    capture_output=True, text=True, timeout=1800)
                installed = proc.returncode == 0
                detail = f"msiexec exit {proc.returncode}"
            except Exception as exc:  # noqa: BLE001
                detail = f"silent install failed: {exc}"
        return ok({"downloaded": result, "installed": installed, "detail": detail,
                   "install": _detect_install(), "plan": plan})

