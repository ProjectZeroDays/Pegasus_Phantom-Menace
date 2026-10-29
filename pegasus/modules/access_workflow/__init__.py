"""
Pegasus Access Workflow Module - Package Initialization

Exposes the dashboard server and all workflow components.
"""

from pegasus.modules.access_workflow.dashboard_server import app as dashboard_app
from pegasus.modules.access_workflow.plugin import metadata, create_plugin, main

__all__ = [
    "dashboard_app",
    "create_plugin",
    "metadata",
    "main",
]

# Expose the Flask app for standalone running
app = dashboard_app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
