"""Passive OSINT search across the catalogue.

Only public, key-authenticated APIs are queried.  A service that needs a key
returns a ``needs_key`` result with the web URL so the operator can run the
query by hand instead.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, List, Optional
from urllib import error, request as urlrequest
from urllib.parse import quote, urlencode

from pegasus.modules.osint import catalog as catalog_mod
from pegasus.modules.osint import config as config_mod

USER_AGENT = "PegasusPhantomMenace/2.2 (authorized security testing)"
TIMEOUT = 25
MAX_RESULTS = 50


def _extract(payload: Any, path: Optional[str]) -> List[Any]:
    if not path:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("results", "hits", "data", "items", "matches", "events"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
        return []
    node: Any = payload
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list) and node:
            node = node[0]
            if isinstance(node, dict):
                node = node.get(part)
        else:
            return []
        if node is None:
            return []
    if isinstance(node, list):
        return node
    return [node]


def _compact(item: Any) -> Dict[str, Any]:
    """Trim a result record down to something a widget can render."""
    if not isinstance(item, dict):
        return {"value": str(item)[:400]}
    keep: Dict[str, Any] = {}
    preferred = (
        "ip", "ip_str", "port", "host", "hostname", "name", "title",
        "domain", "name_value", "value", "organization", "org", "country",
        "country_name", "asn", "product", "server", "type", "severity",
        "risk", "first_seen", "last_seen", "location", "email", "url",
        "matched_field", "tags", "description", "id",
    )
    for key in preferred:
        if key in item and item[key] not in (None, "", [], {}):
            keep[key] = item[key]
    for key, value in item.items():
        if len(keep) >= 8:
            break
        if key not in keep and isinstance(value, (str, int, float, bool)) and value != "":
            keep[key] = value
    return keep or {"value": json.dumps(item)[:400]}


def search(service_id: str, query: str, limit: int = 20) -> Dict[str, Any]:
    """Run one passive query against a catalogue service."""
    try:
        entry = catalog_mod.get(service_id)
    except KeyError:
        return {"ok": False, "error": f"unknown service {service_id}"}

    if entry.get("kind") != "api":
        return {"ok": False, "error": f"{entry.get('name')} is a local tool, not an API",
                "tool": service_id}

    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "query required"}

    key = config_mod.get_key(service_id) or ""
    env_name = entry.get("key_env")
    if not key and env_name:
        import os
        key = os.environ.get(env_name, "").strip()
    if entry.get("key_required") and not key:
        return {
            "ok": False,
            "needs_key": True,
            "error": f"{entry.get('name')} needs an API key",
            "key_env": env_name,
            "url": entry.get("url"),
            "manual_url": f"{entry.get('url')}/search?q={quote(query)}",
        }

    template = entry.get("api") or ""
    url = template.replace("{query}", quote(query))
    url = url.replace("{query_b64}",
                      base64.urlsafe_b64encode(query.encode()).decode().rstrip("="))
    if "{key}" in url:
        url = url.replace("{key}", quote(key))
    elif key and entry.get("key_required"):
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode({'key': key})}"

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    started = time.time()
    try:
        with urlrequest.urlopen(urlrequest.Request(url, headers=headers),
                                timeout=TIMEOUT) as resp:
            raw = resp.read()
            status = resp.status
    except error.HTTPError as exc:
        body = exc.read()[:400].decode("utf-8", "replace")
        return {"ok": False, "error": f"HTTP {exc.code}", "detail": body,
                "service": service_id, "url": url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:240], "service": service_id, "url": url}

    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return {"ok": True, "service": service_id, "query": query,
                "count": 0, "results": [], "note": "response was not JSON",
                "elapsed": round(time.time() - started, 2)}

    items = _extract(payload, entry.get("results"))
    compact = [_compact(item) for item in items[: max(1, min(limit, MAX_RESULTS))]]
    return {
        "ok": True,
        "service": service_id,
        "name": entry.get("name"),
        "query": query,
        "count": len(compact),
        "total": len(items),
        "results": compact,
        "elapsed": round(time.time() - started, 2),
        "source": entry.get("url"),
    }


def search_many(query: str, services: List[str], limit: int = 10) -> Dict[str, Any]:
    """Fan one query out across several catalogue services."""
    out = []
    for service_id in services:
        out.append(search(service_id, query, limit))
    return {"ok": True, "query": query, "services": out}
