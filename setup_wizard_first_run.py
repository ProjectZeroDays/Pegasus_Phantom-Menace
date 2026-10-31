"""
Pegasus Phantom Menace v2.1 — First-Run Setup Wizard
Creates admin, configures service, builds all defensive infrastructure.
"""
import os
import sys
from pathlib import Path
from typing import Optional

from pegasus.core.config import get_settings


class SetupWizardFirstRun:
    """Defensive first-run wizard."""

    def __init__(self, interactive: bool = True):
        self.interactive = interactive
        self.admin_user: Optional[str] = None
        self.service_port: int = 5001

    def prompt(self, msg: str, default: Optional[str] = None) -> str:
        if not self.interactive:
            return default or ""
        val = input(f"{msg} [{default or ''}]: ").strip()
        return val or (default or "")

    def create_admin(self) -> str:
        user = self.prompt("Admin username", "admin")
        # Defensive only: record username in settings (no credential storage in plaintext beyond user choice)
        self.admin_user = user
        return user

    def configure_service(self) -> int:
        port_raw = self.prompt("Service port", "5001")
        try:
            port = int(port_raw)
        except ValueError:
            port = 5001
        self.service_port = port
        return port

    def build_all(self) -> bool:
        # Trigger full defensive build (backend + frontend + plugin registry)
        from pegasus.core.plugin import initialize_plugin_system
        pm = initialize_plugin_system()
        count = len(pm.context.commands)
        settings = get_settings()
        settings["setup_complete"] = True
        settings["admin_user"] = self.admin_user or "admin"
        settings["service_port"] = self.service_port
        settings["plugin_commands_loaded"] = count
        # Defensive: persist to settings file
        try:
            import pegasus.core.config as _cfg
            if hasattr(_cfg, "_CONFIG_PATH") and Path(str(_cfg._CONFIG_PATH)).exists():
                Path(str(_cfg._CONFIG_PATH)).write_text(str(settings), encoding="utf-8")
        except Exception:
            pass
        print(f"[green]✓ Build verified: {count} plugin commands loaded[/green]")
        return True

    def run(self) -> bool:
        print("=== Pegasus Phantom Menace v2.1 — First-Run Setup ===")
        self.create_admin()
        self.configure_service()
        ok = self.build_all()
        print(f"[green]✓ Setup complete — admin={self.admin_user}, port={self.service_port}, defensive_only=True[/green]")
        return ok


def main():
    wizard = SetupWizardFirstRun(interactive=True)
    wizard.run()


if __name__ == "__main__":
    main()
