"""
Pegasus Phantom Menace v2.1 — Setup Init Router
First-run endpoint that triggers wizard and serves setup state.
Defensive: only initializes local config and admin; no external connections.
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from pegasus.core.config import get_settings, save_settings

setup_bp = Blueprint("setup_init", __name__)

@setup_bp.route("/api/setup/init", methods=["POST"])
def init_setup():
    payload = request.get_json(silent=True) or {}
    admin = payload.get("admin") or "admin"
    port = int(payload.get("port") or 5001)
    settings = get_settings()
    settings["setup_complete"] = True
    settings["admin_user"] = admin
    settings["service_port"] = port
    save_settings(settings)
    return jsonify({"ok": True, "admin": admin, "port": port, "setup_complete": True})

@setup_bp.route("/api/setup/state", methods=["GET"])
def setup_state():
    settings = get_settings()
    return jsonify({
        "ok": True,
        "configured": bool(settings.get("setup_complete")),
        "admin": settings.get("admin_user", "admin"),
        "port": settings.get("service_port", 5001),
    })
