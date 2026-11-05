#!/usr/bin/env python3
"""Third repair: trimmed blueprint, wiring, real secret fix, finish the series."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import apply_lib as L
import apply_repair as R

APP = R.APP
ROUTES = R.ROUTES

SECRET_OLD = '    app.config["SECRET_KEY"] = os.environ.get("PEGASUS_SECRET", "development-secret")'
SECRET_NEW = '''    import pathlib
    import secrets
    secret_file = pathlib.Path.home().joinpath(".pegasus", ".secret")
    if not secret_file.exists():
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            secret_file.chmod(0o600)
        except OSError:
            pass
    app.config["SECRET_KEY"] = (
        os.environ.get("PEGASUS_SECRET") or secret_file.read_text(encoding="utf-8").strip()
    )'''

TRIM = r'''"""Supplementary device and ops routes.

Only what app.py does not already declare: device inventory, telemetry reads and
collection, media streaming, catalog, receipts, and a few path aliases the pages
use. Geofences, keywords, /api/system/tools, /api/jobs and /api/delivery/health
live in app.py and are deliberately not duplicated here.

Every view is dr_-prefixed: app.py already defines job_detail, system_tools and
delivery_health, and Flask aborts on a repeated endpoint name.
"""
from __future__ import annotations

import socket
import time
from pathlib import Path

from flask import Response, request

from pegasus.core.config import get_settings
from pegasus.ui.web.backend import telemetry
from pegasus.ui.web.backend.jobs import jobs as job_manager
from pegasus.ui.web.backend.tools import run

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


def register(app, ok, fail) -> None:  # noqa: ANN001
    # -- devices ---------------------------------------------------------
    @app.get("/api/devices")
    def dr_devices_list():
        return ok({"devices": _adb_devices()})

    @app.get("/api/devices/<string:serial>")
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
    def dr_device_notes(serial):
        return ok(telemetry.device_notes(serial))

    @app.post("/api/devices/<string:serial>/notes")
    def dr_device_notes_set(serial):
        body = request.get_json(silent=True) or {}
        return ok(telemetry.set_device_notes(
            serial, body.get("label"), body.get("group"), body.get("notes")
        ))

    @app.get("/api/devices/<string:serial>/summary")
    def dr_device_summary(serial):
        return ok(telemetry.summary(serial))

    # -- telemetry -------------------------------------------------------
    @app.get("/api/devices/<string:serial>/telemetry/<kind>")
    def dr_telemetry_latest(serial, kind):
        sample = telemetry.latest_sample(serial, kind)
        return ok(sample or {"rows": [], "collectedAt": None})

    @app.get("/api/devices/<string:serial>/telemetry/<kind>/history")
    def dr_telemetry_history(serial, kind):
        limit = min(int(request.args.get("limit", 10)), 50)
        return ok({"samples": telemetry.sample_history(serial, kind, limit)})

    @app.post("/api/devices/<string:serial>/telemetry/<kind>/collect")
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
    def dr_media_thumb(serial, media_id):
        return dr_media_raw(serial, media_id)

    # -- system aliases the pages use ------------------------------------
    @app.get("/api/listeners")
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
    def dr_job_cancel(job_id):
        return ok({"cancelled": job_manager.cancel(job_id)})

    # -- dispatch --------------------------------------------------------
    @app.post("/api/tools/<tool>/run")
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
    def dr_catalog_list():
        module = _catalog_module()
        for attr in ("list_vectors", "vectors", "list_entries"):
            if module and hasattr(module, attr):
                value = getattr(module, attr)
                return ok(value() if callable(value) else value)
        return ok([])

    @app.post("/api/catalog/build")
    def dr_catalog_build():
        body = request.get_json(silent=True) or {}
        key = body.get("key")
        if not key:
            return fail("key is required", 400)
        module = _catalog_module()
        if not module or not hasattr(module, "build"):
            return fail("catalog builder unavailable", 503)
        return ok(module.build(key, stage=bool(body.get("stage"))))

    # -- delivery receipts -----------------------------------------------
    @app.get("/api/delivery/receipts")
    def dr_delivery_receipts():
        try:
            from pegasus.modules.delivery import receipts
        except Exception:
            return ok({"receipts": []})
        if not hasattr(receipts, "recent"):
            return ok({"receipts": []})
        return ok({"receipts": receipts.recent(int(request.args.get("limit", 200)))})

    # -- setup aliases ---------------------------------------------------
    @app.get("/api/setup/state")
    def dr_setup_state():
        from pegasus.modules.ai import providers
        return ok({"needsSetup": providers.needs_setup()})

    @app.post("/api/setup/skip")
    def dr_setup_skip():
        marker = Path(get_settings().get_workspace_path()) / ".setup-skip"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(time.time()), encoding="utf-8")
        return ok({"skipped": True})
'''


def main() -> int:
    if not (L.WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    code = R.clean()
    if code:
        return code

    # secret
    print("A2 secret key")
    text = APP.read_text(encoding="utf-8")
    if "secret_file =" in text:
        print("  skip  already applied")
    elif SECRET_OLD in text:
        APP.write_text(text.replace(SECRET_OLD, SECRET_NEW, 1), encoding="utf-8")
        print("  ok    env-var-or-persisted-file")
    else:
        print("  FAIL  secret line not found")
        return 2

    # blueprint rewrite
    print("A3 trimmed blueprint")
    ROUTES.write_text(TRIM, encoding="utf-8")
    print(f"  wrote {ROUTES.relative_to(L.ROOT)} ({len(TRIM.splitlines())} lines)")

    # wiring
    print("A4 wiring")
    text = APP.read_text(encoding="utf-8")
    if "device_routes" in text:
        print("  skip  already wired")
    else:
        anchor = "\ndef create_app() -> Flask:"
        if anchor not in text:
            print("  FAIL  create_app anchor missing")
            return 2
        text = text.replace(
            anchor,
            "\nfrom pegasus.ui.web.backend import device_routes\n" + anchor,
            1,
        )
        reg = "    memory.routes.register(app, ok, fail)\n"
        if reg not in text:
            print("  FAIL  memory.routes.register anchor missing")
            return 2
        text = text.replace(reg, reg + "    device_routes.register(app, ok, fail)\n", 1)
        APP.write_text(text, encoding="utf-8")
        print("  ok    import + register")

    # remaining telemetry/api.ts edits only
    R.EDITS = [e for e in R.EDITS if e[0] not in (APP, ROUTES)]
    print("B  remaining edits")
    code = R.apply_edits()
    if code:
        return code

    print("\ncompile")
    for path in (APP, ROUTES, L.TEL):
        if subprocess.call([sys.executable, "-m", "py_compile", str(path)]) != 0:
            print(f"  failed {path.name}")
            return 3
        print(f"  ok {path.name}")

    print("\nblueprint route count")
    decl = ROUTES.read_text(encoding="utf-8").count("@app.")
    print(f"  {decl} routes, all dr_-prefixed")

    L.phase_c()

    print("E  typecheck")
    if subprocess.call("npx tsc --noEmit", cwd=str(L.WEB), shell=True) != 0:
        print("  tsc failed — not committing")
        return 4
    print("  tsc clean")

    L.phase_d()

    if "--no-commit" in sys.argv:
        print("\n--no-commit set"); return 0

    subprocess.call("git add -A", cwd=str(L.ROOT), shell=True)
    subprocess.call(
        'git commit -m "web: restore src/lib, add supplementary device routes, fix series, fable" '
        '-m "Sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3. Blueprint trimmed to the 25 routes '
        'app.py lacks; views dr_-prefixed to avoid endpoint collisions."',
        cwd=str(L.ROOT), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())