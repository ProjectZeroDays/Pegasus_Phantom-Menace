"""Tool management routes.

Expose the external-tool lifecycle to the web GUI: scan, install one, install
all missing, auto-update all, and OEM USB driver download. Calls into
``pegasus.core.tool_installer`` and ``scripts.driver_downloader``.

Views are tr_-prefixed to avoid collisions with app.py's own view functions.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from flask import request, session

from pegasus.ui.web.backend.tools import scan_tools

AUTH_FLAG = "PEGASUS_REQUIRE_AUTH"
AUTH_TOKEN = "PEGASUS_API_TOKEN"


def _auth_on() -> bool:
    return os.environ.get(AUTH_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _require_token(view):
    import functools

    @functools.wraps(view)
    def wrapper(*a, **k):
        if not _auth_on():
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


def _driver_module():
    """Import scripts.driver_downloader without requiring scripts/ to be a package."""
    scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    spec = importlib.util.spec_from_file_location("driver_downloader", scripts_dir / "driver_downloader.py")
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["driver_downloader"] = mod
    spec.loader.exec_module(mod)
    return mod


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def register(app, ok, fail) -> None:
    """Register all tool-management endpoints."""

    # ── status ───────────────────────────────────────────────────────────
    @app.get("/api/tools/status")
    @_require_token
    def tr_tools_status():
        return ok({"tools": scan_tools()})

    # ── install one ───────────────────────────────────────────────────────
    @app.post("/api/tools/install/<string:key>")
    @_require_token
    def tr_tools_install(key):
        from pegasus.core.tool_installer import install, INSTALLERS
        if key not in INSTALLERS:
            return fail(f"no installer for {key}")
        result = install(key)
        return ok({"tool": result})

    # ── install all missing ───────────────────────────────────────────────
    @app.post("/api/tools/install-all")
    @_require_token
    def tr_tools_install_all():
        from pegasus.core.tool_installer import install_missing
        return ok({"results": install_missing()})

    # ── update all (re-run installers to pick up latest versions) ──────────
    @app.post("/api/tools/update-all")
    @_require_token
    def tr_tools_update_all():
        import subprocess
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
        script = scripts_dir / "tool_autoupdate.py"
        if not script.exists():
            return fail(f"auto-update script not found: {script}")
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=1800,
            )
        except Exception as exc:  # noqa: BLE001
            return fail(f"auto-update failed: {exc}")
        return ok({
            "ok": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "code": proc.returncode,
        })

    # ── driver status ─────────────────────────────────────────────────────
    @app.get("/api/tools/drivers")
    @_require_token
    def tr_tools_drivers():
        manifest = Path.home() / ".pegasus" / "drivers" / "manifest.json"
        if not manifest.exists():
            return ok({"drivers": [], "downloaded": 0, "manifest": None})
        try:
            import json
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            return ok({"drivers": [], "downloaded": 0, "manifest": None})
        return ok({
            "drivers": data.get("results", []),
            "downloaded": data.get("downloaded", 0),
            "total": data.get("drivers", 0),
            "errors": data.get("errors", 0),
            "updated_at": data.get("updated_at"),
            "manifest": str(manifest),
        })

    # ── download drivers ──────────────────────────────────────────────────
    @app.post("/api/tools/drivers/download")
    @_require_token
    def tr_tools_drivers_download():
        mod = _driver_module()
        if mod is None:
            return fail("driver_downloader module not found")
        try:
            rc = mod.main()
        except Exception as exc:  # noqa: BLE001
            return fail(f"driver download failed: {exc}")
        return ok({"ok": rc == 0, "code": rc})
