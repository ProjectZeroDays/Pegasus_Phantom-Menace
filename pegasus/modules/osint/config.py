"""OSINT credential storage.

API keys live in ``~/.pegasus/osint.json`` with owner-only permissions.  The
API surface reports presence only - a key is never echoed back to the browser.
"""
from __future__ import annotations

import json
import os
import pathlib
import stat
from typing import Any, Dict, List

CONFIG_FILE = pathlib.Path.home() / ".pegasus" / "osint.json"


def _read() -> Dict[str, Any]:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: Dict[str, Any]) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def get_key(service_id: str) -> str:
    """The stored key for a service (empty string when absent)."""
    return str(_read().get("keys", {}).get(service_id, "") or "")


def set_key(service_id: str, key: str) -> bool:
    data = _read()
    keys = data.setdefault("keys", {})
    if key:
        keys[service_id] = key
    else:
        keys.pop(service_id, None)
    _write(data)
    return True


def delete_key(service_id: str) -> bool:
    data = _read()
    removed = data.setdefault("keys", {}).pop(service_id, None) is not None
    _write(data)
    return removed


def key_status(service_id: str, env_name: str | None = None) -> Dict[str, Any]:
    """Presence report for a service: configured via file or environment."""
    from_env = bool(os.environ.get(env_name or "", "").strip()) if env_name else False
    from_file = bool(get_key(service_id).strip())
    return {
        "configured": from_env or from_file,
        "source": "environment" if from_env else ("file" if from_file else "none"),
        "env_var": env_name or "",
    }


def all_status(services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for entry in services:
        status = key_status(entry.get("id", ""), entry.get("key_env"))
        out.append({
            "id": entry.get("id"),
            "name": entry.get("name"),
            "key_env": entry.get("key_env"),
            "key_required": bool(entry.get("key_required")),
            **status,
        })
    return out
