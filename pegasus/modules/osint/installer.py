"""Installer for the local OSINT tooling (MimiKATS, IVRE, Maltego).

Python tooling is installed into the interpreter that runs Pegasus, so the
packaged desktop build gets the tool without a separate runtime.  Desktop
applications are downloaded from the vendor's own HTTPS distribution point and
are never redistributed inside the repository - Maltego in particular needs a
commercial licence that only the operator can obtain.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import zipfile
from typing import Any, Dict, List

from pegasus.modules.osint import catalog as catalog_mod

TOOLS_DIR = pathlib.Path.home() / ".pegasus" / "tools"
STATE_FILE = pathlib.Path.home() / ".pegasus" / "tools.json"
PIP_TIMEOUT = 900


def _read() -> Dict[str, Any]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def status(tool_id: str) -> Dict[str, Any]:
    entry = catalog_mod.get(tool_id)
    install = entry.get("install") or {}
    state = _read().get(tool_id, {})
    installed = bool(state.get("installed"))
    path = state.get("path") or ""
    if install.get("type") == "pip" and not installed:
        installed = _pip_module_present(install.get("verify") or install.get("package"))
    detail = state.get("detail") or ""
    if install.get("type") == "pip" and installed and not detail:
        detail = f"importable as {install.get('verify')}"
    return {
        "id": tool_id,
        "name": entry.get("name"),
        "kind": install.get("type"),
        "installed": installed,
        "path": path,
        "version": state.get("version"),
        "detail": detail,
        "license": install.get("license"),
        "notes": entry.get("notes"),
    }


def _pip_module_present(module: str) -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True, timeout=60)
        return proc.returncode == 0
    except Exception:
        return False


def list_status() -> List[Dict[str, Any]]:
    return [status(tool_id) for tool_id in (t["id"] for t in catalog_mod.tools())]


def _pip_install(package: str) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pip", "install", "--quiet",
           "--disable-pip-version-check", package]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PIP_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"pip install timed out after {PIP_TIMEOUT}s"}
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout or "").strip()[-600:]}
    return {"ok": True, "elapsed": round(time.time() - started, 1),
            "output": (proc.stdout or "").strip()[-400:]}


def _download(url: str, target: pathlib.Path) -> Dict[str, Any]:
    from urllib import request as urlrequest
    if not url.lower().startswith("https://"):
        raise ValueError("downloads must use https")
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlrequest.urlopen(urlrequest.Request(url, headers={"User-Agent": "Pegasus/2.2"}),
                            timeout=600) as resp:
        blob = resp.read()
    target.write_bytes(blob)
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def install(tool_id: str, confirm: bool = False) -> Dict[str, Any]:
    """Install one tool. Requires ``confirm`` for anything that writes."""
    entry = catalog_mod.get(tool_id)
    install_spec = entry.get("install")
    if not install_spec:
        return {"ok": False, "error": f"{entry.get('name')} is an online service, not an installable tool"}
    if not confirm:
        return {"ok": False, "needs_confirm": True,
                "plan": {"id": tool_id, "type": install_spec.get("type"),
                         "package": install_spec.get("package"),
                         "url": install_spec.get("url"),
                         "license": install_spec.get("license")}}

    kind = install_spec.get("type")
    if kind == "pip":
        package = install_spec.get("package") or tool_id
        result = _pip_install(package)
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error"), "tool": tool_id}
        state = _read()
        state[tool_id] = {"installed": True, "path": sys.executable,
                          "installed_at": time.time(),
                          "detail": f"pip package {package}",
                          "version": _module_version(install_spec.get("verify") or package)}
        _write(state)
        return {"ok": True, "tool": tool_id, **result}

    if kind == "download":
        url = install_spec.get("url")
        if not url:
            return {"ok": False, "error": "no download url configured"}
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        target = TOOLS_DIR / url.rstrip("/").split("/")[-1]
        try:
            result = _download(url, target)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:300], "tool": tool_id}
        extracted = None
        if target.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(target) as archive:
                    archive.extractall(TOOLS_DIR / tool_id)
                extracted = str(TOOLS_DIR / tool_id)
            except Exception as exc:  # noqa: BLE001
                result["extract_error"] = str(exc)[:200]
        state = _read()
        state[tool_id] = {"installed": True, "path": extracted or str(target),
                          "installed_at": time.time(),
                          "detail": install_spec.get("license") or "downloaded",
                          "sha256": result.get("sha256")}
        _write(state)
        return {"ok": True, "tool": tool_id, **result}

    return {"ok": False, "error": f"unsupported install type {kind}"}


def _module_version(module: str) -> str | None:
    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             f"import importlib.metadata as m; print(m.version('{module}'))"],
            capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None
