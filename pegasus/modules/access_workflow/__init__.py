"""
Pegasus Access Workflow Module - Package Initialization

Exposes the dashboard app and plugin entry points lazily so importing a small
submodule (for example ``zero_click.registry``) does not pull in Flask, the
auth layer or the plugin system.
"""

from __future__ import annotations

from typing import Any

__all__ = ["dashboard_app", "app", "create_plugin", "metadata", "main"]


def __getattr__(name: str) -> Any:
    if name == "dashboard_app" or name == "app":
        from pegasus.modules.access_workflow import dashboard_server

        return dashboard_server.app
    if name in {"create_plugin", "metadata", "main"}:
        from pegasus.modules.access_workflow import plugin

        return getattr(plugin, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    from pegasus.modules.access_workflow import dashboard_server

    dashboard_server.app.run(host="0.0.0.0", port=5050, debug=True)
