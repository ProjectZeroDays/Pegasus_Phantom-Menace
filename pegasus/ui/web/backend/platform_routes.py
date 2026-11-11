"""Platform endpoints the console loads but the backend never served.

The console has always asked for infrastructure health, the service
registry, the payload library, the skill and family catalogues, the
campaign list, the local network identity and the Telegram state.  None
of those endpoints existed on the main application, so every page that
wanted one logged a 404.

Each one is served here from the real source rather than a stub:

  * infrastructure health and the service registry come from the tool
    inventory and the daemon service
  * the payload library is the mass-payload output directory
  * skills and agent families come from the plugin registry
  * campaigns come from the access-workflow campaign manager
  * the network identity comes from the local interface
  * the Telegram state comes from the telegram control module

Every helper is defensive: a source that is not installed yields an empty
result rather than a 500, so the page renders empty instead of failing.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any, Dict, List

from flask import request

HOME = pathlib.Path.home() / ".pegasus"
PAYLOAD_DIR = HOME / "payloads" / "mass"


# ------------------------------------------------------------------ helpers
def _tool_rows() -> List[Dict[str, Any]]:
    try:
        from pegasus.ui.web.backend.tools import scan_tools
    except Exception:
        return []
    try:
        tools = scan_tools()
    except Exception:
        return []
    rows = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        rows.append({
            "name": tool.get("label") or tool.get("key") or "",
            "available": bool(tool.get("available")),
            "key": tool.get("key") or "",
            "path": tool.get("path") or "",
            "purpose": tool.get("purpose") or "",
        })
    return rows


def _listener_rows() -> List[Dict[str, Any]]:
    try:
        from pegasus.ui.web.backend.tools import listener_status
    except Exception:
        return []
    try:
        return list(listener_status() or [])
    except Exception:
        return []


def _daemon_call(*names: str) -> Dict[str, Any]:
    """Call the first available daemon service helper."""
    try:
        from pegasus.modules.access_workflow import daemon_service
    except Exception as exc:
        raise RuntimeError(f"the daemon service module is unavailable: {exc}") from exc
    for name in names:
        fn = getattr(daemon_service, name, None)
        if callable(fn):
            return {"mode": "pegasus", "name": name,
                    "steps": [], "exit": 0, "result": fn()}
    raise RuntimeError("the daemon service module exposes no such helper")


def _plugin_rows() -> List[Dict[str, Any]]:
    """The live plugin registry."""
    plugins: List[Any] = []
    # The application builds its own plugin route from
    # plugin_manager().context.plugins - a dict of name -> plugin.  The
    # import is deferred because app.py imports this module at load time.
    try:
        from pegasus.ui.web.backend.app import plugin_manager
        manager = plugin_manager()
    except Exception:
        manager = None
    if manager is not None:
        context = getattr(manager, "context", None)
        registry = getattr(context, "plugins", None) if context is not None else None
        if isinstance(registry, dict):
            plugins = list(registry.values())
        elif isinstance(registry, (list, tuple)):
            plugins = list(registry)
    if not plugins:
        try:
            from pegasus.core import plugin as plugin_mod
            fn = getattr(plugin_mod, "get_plugin_manager", None)
            if callable(fn):
                manager = fn()
                registry = getattr(getattr(manager, "context", None), "plugins", None)
                if isinstance(registry, dict):
                    plugins = list(registry.values())
        except Exception:
            plugins = []
    rows = []
    for entry in plugins or []:
        meta = getattr(entry, "metadata", None)
        if meta is None and isinstance(entry, dict):
            meta = entry
        if meta is None:
            continue
        get = (lambda key: getattr(meta, key, None)) if not isinstance(meta, dict) \
            else (lambda key: meta.get(key))
        commands = []
        for attr in ("get_commands", "commands"):
            value = getattr(entry, attr, None)
            if callable(value):
                try:
                    commands = list(value().keys()) if isinstance(value(), dict) else list(value())
                except Exception:
                    commands = []
                break
            if isinstance(value, (list, tuple)):
                commands = list(value)
                break
        rows.append({
            "name": get("name") or "",
            "version": get("version") or "",
            "description": get("description") or "",
            "author": get("author") or "",
            "category": get("category") or "general",
            "tags": list(get("tags") or []),
            "provides": list(get("provides") or []),
            "commands": commands,
            "hidden": bool(get("hidden")),
            "internal": bool(get("internal")),
        })
    return rows


def _campaign_rows() -> List[Dict[str, Any]]:
    try:
        from pegasus.modules.access_workflow import campaign_manager
    except Exception:
        return []
    try:
        campaigns = campaign_manager.list_campaigns()
    except Exception:
        return []
    rows = []
    for entry in campaigns or []:
        data = entry.to_dict() if hasattr(entry, "to_dict") else dict(entry or {})
        status = data.get("status")
        rows.append({
            "id": data.get("campaign_id") or data.get("id") or "",
            "name": data.get("name") or "",
            "client": data.get("client") or data.get("author") or "",
            "description": data.get("description") or "",
            "authorization": data.get("authorization") or "written",
            "status": getattr(status, "value", status) or "",
            "created": data.get("created_at") or data.get("created") or "",
            "start_date": data.get("start_date") or "",
        })
    return rows


def _skill_rows() -> List[Dict[str, Any]]:
    rows = []
    for plugin in _plugin_rows():
        if plugin.get("hidden") or plugin.get("internal"):
            continue
        commands = plugin.get("commands") or []
        rows.append({
            "name": plugin.get("name") or "",
            "description": plugin.get("description") or "",
            "trigger": " ".join(plugin.get("tags") or []) or plugin.get("category") or "",
            "category": plugin.get("category") or "general",
            "commands": commands,
            "zeroClickFamilies": list(plugin.get("provides") or []),
        })
    return rows


def _payload_rows() -> List[Dict[str, Any]]:
    rows = []
    if PAYLOAD_DIR.exists():
        for path in sorted(PAYLOAD_DIR.rglob("*")):
            if not path.is_file() or path.suffix.lower() == ".json":
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rows.append({
                "name": path.name,
                "path": str(path),
                "sizeBytes": stat.st_size,
                "modified": stat.st_mtime,
            })
    return rows


def _network_identity() -> Dict[str, Any]:
    ip = ""
    hostname = ""
    try:
        from pegasus.ui.web.backend.tools import local_ip, hostname as host_fn
        ip = local_ip() or ""
        hostname = host_fn() or ""
    except Exception:
        pass
    if not hostname:
        hostname = os.environ.get("COMPUTERNAME") or ""
    return {"ip": ip, "hostname": hostname, "city": "", "country": "", "org": ""}


def _telegram_state() -> Dict[str, Any]:
    bot = None
    chat_id = None
    running = False
    try:
        from pegasus.modules.access_workflow import telegram_control as tc
        for name in ("status", "get_status", "state", "current"):
            fn = getattr(tc, name, None)
            if callable(fn):
                data = fn()
                if isinstance(data, dict):
                    bot = data.get("bot") or data.get("bot_username") or bot
                    chat_id = data.get("chat_id") or data.get("chatId") or chat_id
                    running = bool(data.get("running", running))
                break
    except Exception:
        pass
    if not bot or not chat_id:
        try:
            from pegasus.core.config import get_settings
            section = getattr(get_settings(), "telegram", None)
            if section is not None:
                bot = bot or getattr(section, "bot", None) or \
                    os.environ.get("PEGASUS__TELEGRAM__BOT", "")
                chat_id = chat_id or getattr(section, "chat_id", None) or \
                    os.environ.get("PEGASUS__TELEGRAM__CHAT_ID", "")
        except Exception:
            pass
    return {
        "configured": bool(bot and chat_id),
        "running": running,
        "bot": bot or None,
        "chatId": chat_id or None,
    }


# ------------------------------------------------------------------ routes
def register(app, ok, fail):
    @app.get("/api/infrastructure/health")
    def infrastructure_health():
        tools = _tool_rows()
        services = []
        for listener in _listener_rows():
            services.append({
                "name": listener.get("name") or listener.get("port") or "",
                "healthy": bool(listener.get("listening", listener.get("open", True))),
            })
        available = sum(1 for t in tools if t.get("available"))
        overall = "ok" if (not tools or available == len(tools)) else "degraded"
        return ok({
            "overall": overall,
            "services": services,
            "tools": [{"name": t["name"], "available": t["available"]} for t in tools],
        })

    @app.get("/api/infrastructure/service")
    def infrastructure_service():
        registry = {}
        try:
            from pegasus.modules.access_workflow import daemon_service
            for name in ("service_status", "status", "registered_services"):
                fn = getattr(daemon_service, name, None)
                if callable(fn):
                    data = fn()
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, dict):
                                registry[key] = {
                                    "registered": bool(value.get("registered", value.get("installed", False))),
                                    "detail": str(value.get("detail", "")),
                                }
                            else:
                                registry[key] = {"registered": bool(value), "detail": str(value)}
                    break
        except Exception as exc:
            registry["daemon"] = {"registered": False, "detail": str(exc)}
        return ok(registry)

    @app.post("/api/infrastructure/install")
    def infrastructure_install():
        try:
            result = _daemon_call("install", "install_service", "setup", "install_windows_service")
        except Exception as exc:
            return fail(f"service install unavailable: {exc}", 501)
        return ok({
            "mode": result.get("mode", "pegasus"),
            "name": result.get("name", ""),
            "steps": result.get("steps") or [],
            "exit": result.get("exit", 0),
        })

    @app.post("/api/infrastructure/uninstall")
    def infrastructure_uninstall():
        try:
            result = _daemon_call("uninstall", "uninstall_service", "remove", "remove_windows_service")
        except Exception as exc:
            return fail(f"service uninstall unavailable: {exc}", 501)
        return ok({
            "mode": result.get("mode", "pegasus"),
            "name": result.get("name", ""),
            "steps": result.get("steps") or [],
            "exit": result.get("exit", 0),
        })

    @app.get("/api/payloads")
    def payloads_list():
        return ok({"payloads": _payload_rows(), "directory": str(PAYLOAD_DIR)})

    @app.post("/api/payloads/generate")
    def payloads_generate():
        body = request.get_json(silent=True) or {}
        try:
            from pegasus.modules.access_workflow import mass_payload
        except Exception as exc:
            return fail(f"payload generation unavailable: {exc}", 501)
        try:
            result = mass_payload.generate_batch(
                lhost=body.get("lhost", "127.0.0.1"),
                port=int(body.get("port") or body.get("lport") or 4444),
                count=int(body.get("count") or body.get("iterations") or 1),
                formats=body.get("formats") or ([body["format"]] if body.get("format") else None),
                campaign=body.get("name") or "console",
            )
        except Exception as exc:  # noqa: BLE001
            return fail(f"payload generation failed: {exc}", 502)
        return ok({"manifest": result, "payloads": _payload_rows(),
                   "directory": str(PAYLOAD_DIR)})

    @app.get("/api/skills")
    def skills_list():
        rows = _skill_rows()
        return ok({"skills": rows, "count": len(rows)})

    @app.get("/api/agents/families")
    def agents_families():
        grouped: Dict[str, Dict[str, Any]] = {}
        for skill in _skill_rows():
            key = skill.get("category") or "general"
            row = grouped.setdefault(key, {
                "id": key, "name": key, "skills": [],
                "commands": [], "zeroClickFamilies": [],
            })
            row["skills"].append(skill.get("name") or "")
            for command in skill.get("commands") or []:
                if command not in row["commands"]:
                    row["commands"].append(command)
            for family in skill.get("zeroClickFamilies") or []:
                if family not in row["zeroClickFamilies"]:
                    row["zeroClickFamilies"].append(family)
        families = sorted(grouped.values(), key=lambda r: r["id"])
        return ok({"families": families, "count": len(families)})

    @app.get("/api/campaigns")
    def campaigns_list():
        rows = _campaign_rows()
        stats: Dict[str, Any] = {"total": len(rows)}
        for row in rows:
            key = (row.get("status") or "unknown").lower()
            stats[key] = stats.get(key, 0) + 1
        return ok({"campaigns": rows, "stats": stats})

    @app.get("/api/network/info")
    def network_info():
        return ok(_network_identity())

    @app.get("/api/telegram/status")
    def telegram_status():
        return ok(_telegram_state())
