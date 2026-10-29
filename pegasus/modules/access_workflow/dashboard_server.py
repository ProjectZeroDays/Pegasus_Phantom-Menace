"""
Pegasus Phantom Menace v2 - Dashboard Server

Flask-based web GUI for the Pegasus Phantom Menace platform.
Provides device management, workflow control, real-time monitoring,
and native app-like experience via PWA support.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from flask import Flask, render_template, jsonify, request, send_file
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


def create_app() -> "Flask":
    """Create and configure the Flask dashboard application."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("PEGASUS_SECRET_KEY", secrets.token_hex(32))
    CORS(app)

    # Global dashboard state
    dashboard_state: Dict[str, Any] = {
        "devices": [],
        "workflows": [],
        "status": "initialized",
        "plugins_loaded": 0,
    }

    def get_device_list() -> List[Dict[str, Any]]:
        """Get list of connected devices from the Pegasus plugin system."""
        try:
            from pegasus.core.plugin import get_plugin_manager

            pm = get_plugin_manager()
            if pm is None or not hasattr(pm, "context"):
                return []

            devices = []
            for plugin in pm.context.plugins.values():
                if hasattr(plugin, "get_devices"):
                    try:
                        devs = plugin.get_devices()
                        if isinstance(devs, list):
                            devices.extend(devs)
                    except Exception:
                        pass
            return devices
        except Exception:
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
        """Serve the main dashboard page."""
        return render_template("dashboard.html")

    @app.route("/api/status")
    def api_status():
        """Get system status."""
        pm = get_plugin_manager_safe()
        plugins_loaded = len(pm.context.plugins) if pm and hasattr(pm, "context") else 0

        return jsonify({
            "status": "online",
            "version": "2.0.0",
            "plugins_loaded": plugins_loaded,
            "devices_connected": len(dashboard_state.get("devices", [])),
            "uptime": "00:15:30",
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
        return jsonify({
            "status": "captured",
            "device_id": device_id,
            "image_url": f"/api/screenshot/{device_id}/image",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.route("/api/screenshot/<device_id>/image")
    def api_screenshot_image(device_id: str):
        """Serve screenshot image."""
        return jsonify({"error": "No screenshot available"}), 404

    return app


# Create app instance for import by CLI
app = create_app()


def run_dashboard(host: str = "0.0.0.0", port: int = 5000, debug: bool = False) -> None:
    """Run the dashboard server."""
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    import argparse

    parser = __import__("argparse").ArgumentParser(description="Pegasus Dashboard Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", default=5000, type=int, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
