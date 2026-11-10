"""CVE framework module - catalogue, fingerprinting and passive validators."""
from __future__ import annotations

import json

from pegasus.modules.base import BaseModule
from pegasus.modules.cve import cve_db


class CveModule(BaseModule):
    """CVE catalogue, product fingerprinting and passive exposure validation."""

    @property
    def module_name(self) -> str:
        return "CVE Framework"

    @property
    def module_description(self) -> str:
        return "CVE catalogue, asset fingerprinting and passive host validators"

    @property
    def module_category(self) -> str:
        return "security"

    async def _register_commands(self) -> None:
        self.register_command("cve-search", "Search the offline CVE catalogue", self.cmd_search)
        self.register_command("cve-fingerprint", "Match a product/version inventory", self.cmd_fingerprint)
        self.register_command("cve-validate", "Run a passive host validator", self.cmd_validate)
        self.register_command("cve-list", "List the available validators", self.cmd_list)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="cve_framework",
            component_type="panel",
            path="/cve-framework",
            title="CVE Framework",
            icon="shield",
            order=15,
        )

    async def _register_hooks(self) -> None:
        pass

    async def cmd_search(self, *args) -> None:
        query = str(args[0]) if args else (self.prompt("Search term", default="") or "")
        hits = cve_db.search(query)
        print(json.dumps({"count": len(hits), "hits": hits}, indent=2))

    async def cmd_fingerprint(self, *args) -> None:
        raw = str(args[0]) if args else ""
        assets = []
        for line in raw.splitlines():
            parts = line.strip().split()
            if parts:
                assets.append({"product": parts[0],
                               "version": parts[1] if len(parts) > 1 else ""})
        if not assets:
            self.print_error("usage: cve-fingerprint 'product version' ...")
            return
        print(json.dumps(cve_db.fingerprint(assets), indent=2))

    async def cmd_validate(self, *args) -> None:
        if not args:
            self.print_error("usage: cve-validate <validator-id>")
            return
        try:
            print(json.dumps(cve_db.run_validator(str(args[0])), indent=2))
        except KeyError:
            self.print_error(f"unknown validator: {args[0]}")

    async def cmd_list(self, *args) -> None:
        print(json.dumps(cve_db.validators(), indent=2))
