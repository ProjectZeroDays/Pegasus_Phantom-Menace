"""Supplementary device and ops routes.

Only what app.py does not already declare: device inventory, telemetry reads and
collection, media streaming, catalog, receipts, and a few path aliases the pages
use. Geofences, keywords, /api/system/tools, /api/jobs and /api/delivery/health
live in app.py and are deliberately not duplicated here.

Every view is dr_-prefixed: app.py already defines job_detail, system_tools and
delivery_health, and Flask aborts on a repeated endpoint name.
"""
from __future__ import annotations

import socket

from flask import Response, request, session

from pegasus.core.config import get_settings
from pegasus.ui.web.backend import telemetry
from pegasus.ui.web.backend.jobs import jobs as job_manager
from pegasus.ui.web.backend.tools import run
import pathlib
import os
import platform
import shutil
import subprocess
import sys

KNOWN_PORTS = {
    4444: "meterpreter handler",
    5001: "pegasus api",
    5555: "adb transport",
    55553: "metasploit rpc",
    8080: "http proxy",
    8443: "https proxy",
}

MEDIA_URIS = {
    "photos": "content://media/external/images/media",
    "videos": "content://media/external/video/media",
}


def _adb_devices() -> list[dict]:
    result = run(["adb", "devices", "-l"], timeout=12)
    devices: list[dict] = []
    if not result.get("ok"):
        return devices
    for line in result.get("stdout", "").splitlines()[1:]:
        parts = line.split()
        if not parts or parts[0].startswith("*"):
            continue
        entry = {"serial": parts[0], "state": parts[1] if len(parts) > 1 else "device"}
        for part in parts:
            if part.startswith("model:"):
                entry["model"] = part.split(":", 1)[1]
            elif part.startswith("transport_id:"):
                entry["transport"] = "usb"
        devices.append(entry)
    return devices


def _prop(serial: str, name: str) -> str:
    result = run(["adb", "-s", serial, "shell", "getprop", name], timeout=10)
    return result.get("stdout", "").strip() if result.get("ok") else ""


def _submit(kind: str, title: str, fn, meta: dict | None = None) -> dict:
    job = job_manager.submit(kind, title, fn, meta=meta)
    return {"job": job.to_dict(include_output=False)}


def _catalog_module():
    try:
        from pegasus.modules.access_workflow import catalog
        return catalog
    except Exception:
        return None


AUTH_FLAG = "PEGASUS_REQUIRE_AUTH"
AUTH_TOKEN = "PEGASUS_API_TOKEN"


def _auth_enabled() -> bool:
    """Enforcement is opt-in: without the flag every route stays open."""
    return os.environ.get(AUTH_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _require_token(view):
    """Token header/query, or a logged-in session, when AUTH_FLAG is on."""
    import functools

    @functools.wraps(view)
    def wrapper(*a, **k):
        if not _auth_enabled():
            return view(*a, **k)
        expected = os.environ.get(AUTH_TOKEN, "").strip()
        supplied = (
            request.headers.get("X-Pegasus-Token")
            or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            or request.args.get("token")
            or ""
        ).strip()
        if expected and supplied == expected:
            return view(*a, **k)
        if session.get("pegasus_user") or session.get("user"):
            return view(*a, **k)
        return {"ok": False, "error": "unauthorized"}, 401

    return wrapper


def register(app, ok, fail) -> None:  # noqa: ANN001
    # -- devices ---------------------------------------------------------
    @app.get("/api/devices")
    @_require_token
    def dr_devices_list():
        return ok({"devices": _adb_devices()})

    @app.get("/api/devices/<string:serial>")
    @_require_token
    def dr_device_detail(serial):
        props = {
            "model": _prop(serial, "ro.product.model"),
            "manufacturer": _prop(serial, "ro.product.manufacturer"),
            "androidVersion": _prop(serial, "ro.build.version.release"),
            "sdk": _prop(serial, "ro.build.version.sdk"),
            "patchLevel": _prop(serial, "ro.build.version.security_patch"),
            "buildId": _prop(serial, "ro.build.id"),
            "abi": _prop(serial, "ro.product.cpu.abi"),
        }
        props["serial"] = serial
        props["root"] = bool(
            run(["adb", "-s", serial, "shell", "which", "su"], timeout=8).get("stdout", "").strip()
        )
        props["notes"] = telemetry.device_notes(serial)
        return ok(props)

    @app.get("/api/devices/<string:serial>/notes")
    @_require_token
    def dr_device_notes(serial):
        return ok(telemetry.device_notes(serial))

    @app.post("/api/devices/<string:serial>/notes")
    @_require_token
    def dr_device_notes_set(serial):
        body = request.get_json(silent=True) or {}
        return ok(telemetry.set_device_notes(
            serial, body.get("label"), body.get("group"), body.get("notes")
        ))

    @app.get("/api/devices/<string:serial>/summary")
    @_require_token
    def dr_device_summary(serial):
        return ok(telemetry.summary(serial))

    # -- telemetry -------------------------------------------------------
    @app.get("/api/devices/<string:serial>/telemetry/<kind>")
    @_require_token
    def dr_telemetry_latest(serial, kind):
        sample = telemetry.latest_sample(serial, kind)
        return ok(sample or {"rows": [], "collectedAt": None})

    @app.get("/api/devices/<string:serial>/telemetry/<kind>/history")
    @_require_token
    def dr_telemetry_history(serial, kind):
        limit = min(int(request.args.get("limit", 10)), 50)
        return ok({"samples": telemetry.sample_history(serial, kind, limit)})

    @app.post("/api/devices/<string:serial>/telemetry/<kind>/collect")
    @_require_token
    def dr_telemetry_collect(serial, kind):
        if kind == "media":
            rows = telemetry.collect_media(serial)
            telemetry.save_samples(serial, "photos", rows.get("photos", []))
            telemetry.save_samples(serial, "videos", rows.get("videos", []))
            return ok({"photos": len(rows.get("photos", [])), "videos": len(rows.get("videos", []))})
        rows = telemetry.collect(serial, kind)
        return ok({"kind": kind, "count": len(rows)})

    # -- media -----------------------------------------------------------
    @app.get("/api/devices/<string:serial>/media/<int:media_id>/raw")
    @_require_token
    def dr_media_raw(serial, media_id):
        import subprocess
        # exec-out keeps stdout byte-exact; `shell` mangles anything above 0x7F.
        for uri in MEDIA_URIS.values():
            proc = subprocess.run(
                ["adb", "-s", serial, "exec-out", "content", "read", "--uri", f"{uri}/{media_id}"],
                capture_output=True,
                timeout=120,
            )
            if proc.returncode == 0 and proc.stdout:
                magic = proc.stdout[:8]
                if magic[:3] == b"\xff\xd8\xff":
                    mime = "image/jpeg"
                elif magic[:4] == b"\x89PNG":
                    mime = "image/png"
                elif magic[4:8] == b"ftyp":
                    mime = "video/mp4"
                else:
                    mime = "application/octet-stream"
                return Response(proc.stdout, mimetype=mime)
        return fail("media unavailable", 404)

    @app.get("/api/devices/<string:serial>/media/<int:media_id>/thumb")
    @_require_token
    def dr_media_thumb(serial, media_id):
        return dr_media_raw(serial, media_id)

    # -- system aliases the pages use ------------------------------------
    @app.get("/api/listeners")
    @_require_token
    def dr_listeners():
        rows = []
        for port, service in KNOWN_PORTS.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.15)
            try:
                is_open = sock.connect_ex(("127.0.0.1", port)) == 0
            finally:
                sock.close()
            rows.append({"host": "127.0.0.1", "port": port, "open": is_open, "service": service})
        return ok({"listeners": rows})

    @app.get("/api/system/info")
    @_require_token
    def dr_system_info():
        import platform
        import shutil
        return ok({
            "host": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "adb": bool(shutil.which("adb")),
            "workspace": str(get_settings().get_workspace_path()),
        })

    # -- jobs ------------------------------------------------------------
    @app.delete("/api/jobs/<string:job_id>")
    @_require_token
    def dr_job_cancel(job_id):
        return ok({"cancelled": job_manager.cancel(job_id)})

    # -- dispatch --------------------------------------------------------
    @app.post("/api/tools/<tool>/run")
    @_require_token
    def dr_tool_run(tool):
        body = request.get_json(silent=True) or {}
        args = [str(a) for a in (body.get("args") or [])]
        return ok(
            _submit(
                f"tool:{tool}",
                f"{tool} {' '.join(args)}".strip(),
                lambda ctx: run([tool, *args], timeout=600),
                meta={"tool": tool, "args": args},
            ),
            202,
        )

    @app.post("/api/network/scan")
    @_require_token
    def dr_network_scan():
        body = request.get_json(silent=True) or {}
        target = body.get("target") or "192.168.1.0/24"
        ports = body.get("ports") or "1-1000"

        def work(ctx):
            result = run(["nmap", "-sV", "-T4", "-p", ports, target], timeout=1800)
            hosts = []
            current = None
            for line in result.get("stdout", "").splitlines():
                if line.startswith("Nmap scan report for "):
                    current = {"host": line.split("for ")[-1].strip(), "ports": []}
                    hosts.append(current)
                elif current and "/tcp" in line:
                    fields = line.split()
                    current["ports"].append({
                        "port": int(fields[0].split("/")[0]),
                        "protocol": "tcp",
                        "state": fields[1] if len(fields) > 1 else "unknown",
                        "service": fields[2] if len(fields) > 2 else "",
                    })
            return {"hosts": hosts}

        return ok(_submit("network:scan", f"nmap {target}", work, meta={"target": target}), 202)

    # -- catalog ---------------------------------------------------------
    @app.get("/api/catalog")
    @_require_token
    def dr_catalog_list():
        module = _catalog_module()
        for attr in ("list_vectors", "vectors", "list_entries"):
            if module and hasattr(module, attr):
                value = getattr(module, attr)
                return ok(value() if callable(value) else value)
        return ok([])

    @app.post("/api/catalog/build")
    @_require_token
    def dr_catalog_build():
        body = request.get_json(silent=True) or {}
        key = body.get("key")
        if not key:
            return fail("key is required", 400)
        module = _catalog_module()
        if not module or not hasattr(module, "build"):
            return fail("catalog builder unavailable", 503)
        return ok(module.build(key, stage=bool(body.get("stage"))))

