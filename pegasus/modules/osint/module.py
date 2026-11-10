"""OSINT module - search engines, attack surface and local tooling."""
from __future__ import annotations

import json

from pegasus.modules.base import BaseModule
from pegasus.modules.osint import catalog as catalog_mod
from pegasus.modules.osint import config as config_mod
from pegasus.modules.osint import installer as installer_mod
from pegasus.modules.osint import search as search_mod


class OsintModule(BaseModule):
    """Passive OSINT search across the catalogue, plus local tooling."""

    @property
    def module_name(self) -> str:
        return "OSINT Search Engines"

    @property
    def module_description(self) -> str:
        return ("Code, attack-surface, threat-intelligence, server and WiFi "
                "OSINT search engines with configurable API keys, plus the "
                "MimiKATS, IVRE and Maltego tooling")

    @property
    def module_category(self) -> str:
        return "intelligence"

    async def _register_commands(self) -> None:
        self.register_command("osint-catalog", "List the OSINT service catalogue", self.cmd_catalog)
        self.register_command("osint-search", "Run a passive OSINT query", self.cmd_search)
        self.register_command("osint-tools", "Show the local tooling status", self.cmd_tools)
        self.register_command("osint-install", "Install a local OSINT tool", self.cmd_install)
        self.register_command("osint-key", "Set or clear a service API key", self.cmd_key)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="osint_search",
            component_type="panel",
            path="/osint",
            title="OSINT Search Engines",
            icon="search",
            order=12,
        )
        self.register_ui_component(
            name="osint_tools",
            component_type="panel",
            path="/osint/tools",
            title="OSINT Tooling",
            icon="toolbox",
            order=13,
        )

    async def _register_hooks(self) -> None:
        pass

    async def cmd_catalog(self, *args) -> None:
        print(json.dumps({
            "categories": [{"id": cid, "label": label}
                           for cid, label in catalog_mod.CATEGORIES],
            "services": [{"id": s["id"], "name": s["name"],
                          "category": s["category"], "kind": s["kind"]}
                         for s in catalog_mod.catalog()],
        }, indent=2))

    async def cmd_search(self, *args) -> None:
        if len(args) < 2:
            self.print_error("usage: osint-search <service-id> <query>")
            return
        result = search_mod.search(str(args[0]), str(args[1]))
        print(json.dumps(result, indent=2))

    async def cmd_tools(self, *args) -> None:
        print(json.dumps(installer_mod.list_status(), indent=2))

    async def cmd_install(self, *args) -> None:
        if not args:
            self.print_error("usage: osint-install <tool-id>")
            return
        result = installer_mod.install(str(args[0]), confirm=True)
        print(json.dumps(result, indent=2))

    async def cmd_key(self, *args) -> None:
        if len(args) < 2:
            self.print_error("usage: osint-key <service-id> <key|clear>")
            return
        service_id = str(args[0])
        value = str(args[1])
        if value.lower() in ("clear", "none", "-"):
            config_mod.delete_key(service_id)
            print(f"cleared key for {service_id}")
        else:
            config_mod.set_key(service_id, value)
            print(f"stored key for {service_id}")
