"""Background daemon control and startup registration.

The daemon runs the web backend detached from the console so the UI can be
reopened without restarting the stack.  Startup registration uses the Windows
Task Scheduler and is only performed when the operator explicitly confirms.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.auth import operator

STATE_FILE = pathlib.Path.home() / ".pegasus" / "daemon.json"
LOG_FILE = pathlib.Path.home() / ".pegasus" / "daemon.log"
TASK_NAME = "PegasusPhantomMenaceDaemon"


def _read() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return False
    return str(pid) in out


def _launcher() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "start_server.py"
        if candidate.is_file():
            return candidate
    return pathlib.Path("start_server.py")


def register(app, ok, fail):
    @app.get("/api/daemon/status")
    @operator.require("viewer")
    def daemon_status():
        state = _read()
        pid = int(state.get("pid") or 0)
        running = _alive(pid)
        if not running and pid:
            state["pid"] = 0
            _write(state)
        return ok({"running": running, "pid": pid if running else 0,
                   "port": state.get("port"), "autostart": state.get("autostart", False),
                   "log": str(LOG_FILE), "task": TASK_NAME})

    @app.post("/api/daemon/start")
    @operator.require("admin")
    def daemon_start():
        state = _read()
        pid = int(state.get("pid") or 0)
        if _alive(pid):
            return fail("daemon already running", 409)
        launcher = _launcher()
        if not launcher.is_file():
            return fail("start_server.py not found", 404)
        port = int(state.get("port") or 5095)
        env = dict(os.environ)
        env["PEGASUS_PORT"] = str(port)
        try:
            handle = LOG_FILE.open("a", encoding="utf-8")
            proc = subprocess.Popen([sys.executable, str(launcher)],
                                    stdout=handle, stderr=subprocess.STDOUT,
                                    env=env, cwd=str(launcher.parent),
                                    creationflags=0x08000000)
        except Exception as exc:  # noqa: BLE001
            return fail(f"cannot start daemon: {exc}", 500)
        state["pid"] = proc.pid
        state["port"] = port
        state["started"] = time.time()
        _write(state)
        return ok({"pid": proc.pid, "port": port, "log": str(LOG_FILE)})

    @app.post("/api/daemon/stop")
    @operator.require("admin")
    def daemon_stop():
        state = _read()
        pid = int(state.get("pid") or 0)
        if not _alive(pid):
            state["pid"] = 0
            _write(state)
            return ok({"stopped": False, "detail": "daemon was not running"})
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"],
                           capture_output=True, text=True, timeout=60)
        except Exception as exc:  # noqa: BLE001
            return fail(f"cannot stop daemon: {exc}", 500)
        state["pid"] = 0
        _write(state)
        return ok({"stopped": True, "pid": pid})

    @app.get("/api/daemon/autostart")
    @operator.require("viewer")
    def autostart_get():
        state = _read()
        return ok({"autostart": bool(state.get("autostart")),
                   "task": TASK_NAME})

    @app.post("/api/daemon/autostart")
    @operator.require("admin")
    def autostart_set():
        body = request.get_json(silent=True) or {}
        enabled = bool(body.get("enabled", True))
        if not body.get("confirm"):
            return fail("startup registration requires confirm=true", 409)
        state = _read()
        if enabled:
            launcher = _launcher()
            cmd = ["schtasks", "/Create", "/F", "/TN", TASK_NAME, "/TR",
                   f'"{sys.executable}" "{launcher}"', "/SC", "ONLOGON"]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            except Exception as exc:  # noqa: BLE001
                return fail(f"schtasks failed: {exc}", 500)
            state["autostart"] = True
            state["autostart_output"] = (proc.stdout or "").strip()[:400]
        else:
            try:
                subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
                               capture_output=True, text=True, timeout=60)
            except Exception as exc:  # noqa: BLE001
                return fail(f"schtasks failed: {exc}", 500)
            state["autostart"] = False
        _write(state)
        return ok({"autostart": state["autostart"], "task": TASK_NAME})
