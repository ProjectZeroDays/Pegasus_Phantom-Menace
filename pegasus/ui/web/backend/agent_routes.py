"""AI agent configuration routes.

Reads the globally installed opencode provider configuration (the same file
opencode itself uses), reports which providers have a usable credential, and
auto-configures the Pegasus AI settings from it.

Credentials are never echoed back to the browser: only presence is reported.
The selected key is written into the application ``.env`` so the running
backend picks it up via ``pydantic-settings`` (``env_nested_delimiter="__"``,
so ``PEGASUS__AI__API_KEY`` lands in ``Settings.ai.api_key``).
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import request

AGENT_STATE = Path.home() / ".pegasus" / "agents.json"
ENV_RE = re.compile(r"^\{env:(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}$")


# ---------------------------------------------------------------------------
# opencode config discovery
# ---------------------------------------------------------------------------

def _opencode_config_paths() -> List[Path]:
    paths: List[Path] = []
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        paths.append(Path(xdg) / "opencode" / "opencode.json")
    home = Path.home()
    paths.append(home / ".config" / "opencode" / "opencode.json")
    paths.append(home / ".opencode" / "opencode.json")
    return paths


def _opencode_config() -> tuple[Optional[Path], Dict[str, Any]]:
    for path in _opencode_config_paths():
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                return path, data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            continue
    return None, {}


def _resolve_key(raw: Any) -> tuple[Optional[str], bool]:
    """Return (secret, present) for an apiKey value.

    Supports literal keys and the opencode ``{env:VAR}`` indirection.
    """
    if not isinstance(raw, str) or not raw:
        return None, False
    match = ENV_RE.match(raw.strip())
    if match:
        name = match.group("name")
        value = os.environ.get(name)
        return value, bool(value)
    if raw.startswith("{env:"):
        return None, False
    return raw, True


def _providers() -> List[Dict[str, Any]]:
    _, config = _opencode_config()
    out: List[Dict[str, Any]] = []
    providers = config.get("provider") or {}
    if not isinstance(providers, dict):
        return out
    for pid, spec in providers.items():
        spec = spec if isinstance(spec, dict) else {}
        options = spec.get("options") if isinstance(spec.get("options"), dict) else {}
        models = spec.get("models") if isinstance(spec.get("models"), dict) else {}
        secret, present = _resolve_key(options.get("apiKey"))
        out.append({
            "id": pid,
            "name": spec.get("name") or pid,
            "baseUrl": options.get("baseURL") or "",
            "apiKeyRef": options.get("apiKey") or "",
            "hasKey": present,
            "keyPresent": present,
            "models": [{"id": mid, "name": (m or {}).get("name", mid)} for mid, m in models.items()],
        })
    return out


def _agent_state() -> Dict[str, Any]:
    try:
        if AGENT_STATE.is_file():
            data = json.loads(AGENT_STATE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"agent": None, "provider": None, "model": None, "skills": ".openfable-skills"}


def _save_agent_state(state: Dict[str, Any]) -> None:
    AGENT_STATE.parent.mkdir(parents=True, exist_ok=True)
    AGENT_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _env_path() -> Path:
    """The application .env - cwd first, then the repository root."""
    candidates = [Path.cwd() / ".env"]
    try:
        from pegasus.core.config import _repo_root  # type: ignore

        candidates.append(Path(_repo_root()) / ".env")
    except Exception:
        pass
    candidates.append(Path(__file__).resolve().parents[4] / ".env")
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def _write_env(values: Dict[str, str]) -> Path:
    """Upsert keys into the application .env, preserving unrelated entries."""
    path = _env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: List[str] = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    remaining = dict(values)
    out: List[str] = []
    for line in existing:
        stripped = line.strip()
        matched = False
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                matched = True
        if not matched:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    return path


def register(app, ok, fail):
    @app.get("/api/agents/available")
    def agents_available():
        config_path, _ = _opencode_config()
        providers = _providers()
        return ok({
            "opencode": bool(shutil.which("opencode")),
            "mimicode": bool(shutil.which("mimicode")),
            "configPath": str(config_path) if config_path else "",
            "providers": providers,
            "providerCount": len(providers),
            "providersWithKey": sum(1 for p in providers if p["hasKey"]),
        })

    @app.get("/api/agents/config")
    def agents_config_get():
        state = _agent_state()
        try:
            from pegasus.core.config import get_settings

            ai = get_settings().ai
            state.setdefault("aiProvider", ai.provider)
            state.setdefault("aiModel", ai.model)
            state.setdefault("aiConfigured", bool(ai.api_key))
        except Exception:
            pass
        return ok(state)

    @app.post("/api/agents/config")
    def agents_config_set():
        body = request.get_json(silent=True) or {}
        state = _agent_state()
        for key in ("agent", "provider", "model", "skills"):
            if key in body:
                state[key] = body[key]
        _save_agent_state(state)
        return ok({"config": state})

    @app.post("/api/agents/autoconfigure")
    def agents_autoconfigure():
        """Pick a provider that actually has a credential and persist it.

        Preference order: the provider already recorded in the agent state,
        then the first provider (in opencode config order) whose key is set.
        """
        providers = _providers()
        if not providers:
            return fail("no opencode provider configuration found", 404)

        state = _agent_state()
        preferred = state.get("provider")
        ordered = sorted(
            providers,
            key=lambda p: (0 if p["id"] == preferred else 1, 0 if p["hasKey"] else 1),
        )
        chosen = next((p for p in ordered if p["hasKey"]), None)
        if chosen is None:
            return fail("no provider has a credential in the environment", 409)

        secret, present = _resolve_key(
            (chosen.get("apiKeyRef") or None)
        )
        if not present:
            return fail("selected provider has no credential", 409)

        model = chosen["models"][0]["id"] if chosen["models"] else ""
        if state.get("model") and any(m["id"] == state["model"] for m in chosen["models"]):
            model = state["model"]

        env_values = {
            "PEGASUS__AI__PROVIDER": chosen["id"],
            "PEGASUS__AI__MODEL": model,
            "PEGASUS__AI__API_KEY": secret or "",
        }
        if chosen.get("baseUrl"):
            env_values["PEGASUS__AI__BASE_URL"] = chosen["baseUrl"]

        env_path = _write_env(env_values)

        state.update({
            "agent": state.get("agent") or ("opencode" if shutil.which("opencode") else None),
            "provider": chosen["id"],
            "model": model,
        })
        _save_agent_state(state)

        # Refresh the in-process settings so the change applies immediately.
        try:
            from pegasus.core.config import get_settings

            get_settings().clear_cache()
        except Exception:
            pass
        for key, value in env_values.items():
            os.environ[key] = value

        return ok({
            "configured": True,
            "provider": chosen["id"],
            "providerName": chosen["name"],
            "model": model,
            "baseUrl": chosen.get("baseUrl", ""),
            "envFile": str(env_path),
            "written": sorted(env_values),
            "keyStored": True,
        })
