#!/usr/bin/env python3
"""
Pegasus Phantom Menace v2 - Daemon Service

Keeps the dashboard alive: supervised start/stop, exponential-backoff restart,
HTTP health checks and host-level installation (Windows service via NSSM or a
scheduled task).

State is written to ``~/.pegasus/daemon/state.json`` so a CLI invocation can
report on a daemon started by another process.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

STATE_DIR = Path.home() / ".pegasus" / "daemon"
STATE_FILE = STATE_DIR / "state.json"
LOG_FILE = STATE_DIR / "daemon.log"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DaemonService:
    """Supervises the dashboard server process."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5050):
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.restarts = 0
        self.max_restarts = 20
        self.started_at: Optional[float] = None
        self.last_error: Optional[str] = None

    # -- paths --------------------------------------------------------------
    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def dashboard_script(self) -> Path:
        return self.project_root / "pegasus" / "modules" / "access_workflow" / "dashboard_server.py"

    # -- state --------------------------------------------------------------
    def _write_state(self, **extra: Any) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state = self.status()
        state.update(extra)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def status(self) -> Dict[str, Any]:
        running = self.process is not None and self.process.poll() is None
        uptime = int(time.time() - self.started_at) if running and self.started_at else 0
        return {
            "running": running,
            "pid": self.process.pid if running else None,
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}/",
            "restarts": self.restarts,
            "uptime_seconds": uptime,
            "healthy": self.health_check(),
            "last_error": self.last_error,
            "checked_at": _now(),
        }

    def health_check(self, timeout: float = 2.0) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> Dict[str, Any]:
        if self.process is not None and self.process.poll() is None:
            return self.status()
        if not self.dashboard_script.exists():
            self.last_error = f"dashboard script missing: {self.dashboard_script}"
            return self.status()

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log = LOG_FILE.open("ab")
        log.write(f"\n=== start {_now()} ===\n".encode())
        log.flush()
        try:
            self.process = subprocess.Popen(
                [sys.executable, str(self.dashboard_script), "--host", self.host, "--port", str(self.port)],
                cwd=str(self.project_root),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except OSError as exc:
            self.last_error = str(exc)
            return self.status()

        self.started_at = time.time()
        for _ in range(20):
            if self.health_check(0.5):
                break
            time.sleep(0.25)
        self._write_state()
        return self.status()

    def stop(self, timeout: int = 10) -> Dict[str, Any]:
        self._stop.set()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.started_at = None
        self._write_state()
        return self.status()

    def restart(self) -> Dict[str, Any]:
        self.stop()
        time.sleep(1)
        self.restarts += 1
        return self.start()

    # -- supervision --------------------------------------------------------
    def supervise(self, interval: int = 5) -> None:
        """Restart the dashboard on crash with exponential backoff."""
        self._stop.clear()
        backoff = 2
        while not self._stop.is_set():
            if self.process is not None and self.process.poll() is not None:
                self.restarts += 1
                if self.restarts > self.max_restarts:
                    self.last_error = "max restarts exceeded"
                    self._write_state()
                    return
                self.last_error = f"child exited with {self.process.returncode}"
                self._write_state()
                time.sleep(min(backoff, 30))
                backoff = min(backoff * 2, 30)
                self.start()
            else:
                backoff = 2
            self._stop.wait(interval)

    def start_supervisor(self, interval: int = 5) -> None:
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        self.monitor_thread = threading.Thread(target=self.supervise, args=(interval,), daemon=True, name="pegasus-daemon-supervisor")
        self.monitor_thread.start()

    # -- installation -------------------------------------------------------
    def install_service(self, name: str = "PegasusDaemon") -> Dict[str, Any]:
        """Register a Windows service (NSSM) or scheduled task as fallback."""
        script = str(Path(__file__).resolve())
        if shutil.which("nssm"):
            commands = [
                ["nssm", "install", name, sys.executable, script, "--host", self.host, "--port", str(self.port)],
                ["nssm", "set", name, "Start", "SERVICE_AUTO_START"],
                ["nssm", "start", name],
            ]
            mode = "windows-service"
        else:
            commands = [
                ["schtasks", "/Create", "/TN", name, "/SC", "ONSTART", "/RL", "HIGHEST",
                 "/TR", f'"{sys.executable}" "{script}" --host {self.host} --port {self.port}', "/F"],
                ["schtasks", "/Run", "/TN", name],
            ]
            mode = "scheduled-task"
        output = []
        for command in commands:
            proc = subprocess.run(command, capture_output=True, text=True)
            output.append({"command": " ".join(command), "exit": proc.returncode, "out": (proc.stdout or proc.stderr).strip()[:500]})
        return {"mode": mode, "name": name, "steps": output}

    def uninstall_service(self, name: str = "PegasusDaemon") -> Dict[str, Any]:
        if shutil.which("nssm"):
            subprocess.run(["nssm", "stop", name], capture_output=True)
            proc = subprocess.run(["nssm", "remove", name, "confirm"], capture_output=True, text=True)
            mode = "windows-service"
        else:
            proc = subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, text=True)
            mode = "scheduled-task"
        return {"mode": mode, "name": name, "exit": proc.returncode, "out": (proc.stdout or proc.stderr).strip()[:500]}


_daemon: Optional[DaemonService] = None


def get_daemon(host: str = "127.0.0.1", port: int = 5050) -> DaemonService:
    global _daemon
    if _daemon is None:
        _daemon = DaemonService(host=host, port=port)
    return _daemon


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pegasus daemon service")
    parser.add_argument("action", nargs="?", default="run", choices=["run", "start", "stop", "restart", "status", "install", "uninstall"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--name", default="PegasusDaemon")
    args = parser.parse_args()

    daemon = get_daemon(args.host, args.port)
    if args.action == "run":
        daemon.start()
        daemon.start_supervisor()
        print(json.dumps(daemon.status(), indent=2))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            daemon.stop()
    elif args.action == "install":
        print(json.dumps(daemon.install_service(args.name), indent=2))
    elif args.action == "uninstall":
        print(json.dumps(daemon.uninstall_service(args.name), indent=2))
    else:
        print(json.dumps(getattr(daemon, args.action)(), indent=2))


if __name__ == "__main__":
    main()
