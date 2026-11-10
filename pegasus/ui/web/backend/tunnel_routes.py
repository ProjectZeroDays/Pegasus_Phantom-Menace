"""Public tunnel control for ngrok and cloudflared.

Both binaries are executed with an explicit command line and their public URL
is read back from their own output.  Nothing is installed automatically and
no token is stored in the clear - the operator's own environment is used.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.auth import operator

STATE_FILE = pathlib.Path.home() / ".pegasus" / "tunnels.json"
LOG_DIR = pathlib.Path.home() / ".pegasus" / "tunnel-logs"

NGROK_URL = re.compile(r"https://[a-z0-9.-]+\.ngrok(?:-free)?\.(?:app|io)")
CF_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _read() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    local = pathlib.Path.home() / ".pegasus" / "bin" / (name + ".exe")
    return str(local) if local.is_file() else ""


def _pids(provider: str) -> List[int]:
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {provider}.exe"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return []
    pids = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) > 1 and parts[1].isdigit():
            pids.append(int(parts[1]))
    return pids


def register(app, ok, fail):
    @app.get("/api/tunnels/status")
    @operator.require("viewer")
    def tunnels_status():
        state = _read()
        providers = []
        for provider in ("ngrok", "cloudflared"):
            meta = state.get(provider, {})
            binary = _binary(provider)
            pids = _pids(provider)
            providers.append({
                "id": provider,
                "installed": bool(binary),
                "binary": binary,
                "running": bool(pids),
                "pids": pids,
                "public_url": meta.get("public_url"),
                "port": meta.get("port"),
                "started": meta.get("started"),
            })
        return ok({"providers": providers})

    @app.post("/api/tunnels/<provider>/start")
    @operator.require("admin")
    def tunnel_start(provider: str):
        if provider not in ("ngrok", "cloudflared"):
            return fail("unknown provider", 404)
        body = request.get_json(silent=True) or {}
        try:
            port = int(body.get("port") or 5095)
        except (TypeError, ValueError):
            return fail("port must be numeric")
        binary = _binary(provider)
        if not binary:
            return fail(f"{provider} is not installed", 409)
        if _pids(provider):
            return fail(f"{provider} is already running", 409)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"{provider}.log"
        if provider == "ngrok":
            cmd = [binary, "http", str(port), "--log=stdout"]
        else:
            cmd = [binary, "tunnel", "--url", f"http://127.0.0.1:{port}"]
        try:
            handle = log_path.open("w", encoding="utf-8")
            proc = subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT,
                                    cwd=str(LOG_DIR))
        except Exception as exc:  # noqa: BLE001
            return fail(f"cannot start {provider}: {exc}", 500)
        url = None
        deadline = time.time() + 25
        while time.time() < deadline:
            time.sleep(1)
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            match = NGROK_URL.search(text) or CF_URL.search(text)
            if match:
                url = match.group(0)
                break
        state = _read()
        state[provider] = {"pid": proc.pid, "port": port, "public_url": url,
                           "started": time.time(), "log": str(log_path)}
        _write(state)
        return ok({"provider": provider, "pid": proc.pid, "public_url": url,
                   "log": str(log_path)})

    @app.post("/api/tunnels/<provider>/stop")
    @operator.require("admin")
    def tunnel_stop(provider: str):
        if provider not in ("ngrok", "cloudflared"):
            return fail("unknown provider", 404)
        state = _read()
        meta = state.get(provider, {})
        pids = _pids(provider)
        if meta.get("pid"):
            pids = list({*pids, int(meta["pid"])})
        stopped = []
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, text=True, timeout=30)
                stopped.append(pid)
            except Exception:
                continue
        state.pop(provider, None)
        _write(state)
        return ok({"provider": provider, "stopped": stopped})
