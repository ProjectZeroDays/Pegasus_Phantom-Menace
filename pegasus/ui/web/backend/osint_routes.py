"""OSINT search engine routes.

Exposes the service catalogue, runs passive queries, manages API keys and
drives the local tool installer (MimiKATS, IVRE, Maltego).  API keys are
stored server side and are never echoed back - only presence is reported.
"""
from __future__ import annotations

from flask import request

from pegasus.modules.osint import catalog as catalog_mod
from pegasus.modules.osint import config as config_mod
from pegasus.modules.osint import installer as installer_mod
from pegasus.modules.osint import search as search_mod


def register(app, ok, fail):
    @app.get("/api/osint/catalog")
    def osint_catalog():
        services = catalog_mod.catalog()
        keys = {row["id"]: row for row in config_mod.all_status(services)}
        entries = []
        for service in services:
            item = dict(service)
            status = keys.get(service["id"], {})
            item["key_configured"] = bool(status.get("configured"))
            item["key_source"] = status.get("source", "none")
            entries.append(item)
        return ok({
            "categories": [{"id": cid, "label": label}
                           for cid, label in catalog_mod.CATEGORIES],
            "services": entries,
            "count": len(entries),
        })

    @app.post("/api/osint/search")
    def osint_search():
        body = request.get_json(silent=True) or {}
        service = str(body.get("service") or "").strip()
        query = str(body.get("query") or "").strip()
        if not service:
            return fail("service required")
        if not query:
            return fail("query required")
        limit = int(body.get("limit") or 20)
        result = search_mod.search(service, query, limit)
        if result.get("needs_key"):
            return ok(result)
        if not result.get("ok"):
            return fail(result.get("error") or "search failed", 502, result=result)
        return ok(result)

    @app.post("/api/osint/search/many")
    def osint_search_many():
        body = request.get_json(silent=True) or {}
        query = str(body.get("query") or "").strip()
        services = body.get("services") or []
        if not query:
            return fail("query required")
        if not isinstance(services, list) or not services:
            return fail("services required")
        return ok(search_mod.search_many(query, [str(s) for s in services][:8],
                                         int(body.get("limit") or 10)))

    @app.get("/api/osint/tools")
    def osint_tools():
        return ok({"tools": installer_mod.list_status(),
                   "tools_dir": str(installer_mod.TOOLS_DIR)})

    @app.post("/api/osint/tools/<tool_id>/install")
    def osint_tool_install(tool_id: str):
        body = request.get_json(silent=True) or {}
        try:
            result = installer_mod.install(tool_id, confirm=bool(body.get("confirm")))
        except KeyError:
            return fail("unknown tool", 404)
        if result.get("needs_confirm"):
            return ok(result)
        if not result.get("ok"):
            return fail(result.get("error") or "install failed", 502, result=result)
        return ok(result)

    @app.get("/api/osint/keys")
    def osint_keys():
        return ok({"keys": config_mod.all_status(catalog_mod.catalog())})

    @app.post("/api/osint/keys")
    def osint_key_set():
        body = request.get_json(silent=True) or {}
        service = str(body.get("service") or "").strip()
        key = str(body.get("key") or "")
        if not service:
            return fail("service required")
        try:
            entry = catalog_mod.get(service)
        except KeyError:
            return fail("unknown service", 404)
        if not entry.get("key_env"):
            return fail(f"{entry.get('name')} does not use an API key", 400)
        config_mod.set_key(service, key)
        return ok({"service": service,
                   "configured": bool(key),
                   "env_var": entry.get("key_env")})

    @app.delete("/api/osint/keys/<service_id>")
    def osint_key_delete(service_id: str):
        removed = config_mod.delete_key(service_id)
        return ok({"service": service_id, "removed": removed})
