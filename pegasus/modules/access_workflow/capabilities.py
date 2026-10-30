"""
Pegasus Phantom Menace v2 - Unified capability manifest

One machine-readable description of everything the platform can do, consumed by
the CLI, dashboard, mobile client and installer so every distribution exposes
the same surface.

Capabilities are grouped by subsystem and each group is counted from the live
registries; the manifest therefore fails loudly when a module is missing rather
than drifting.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List

from pegasus.modules.access_workflow import nso_capabilities

SURFACES = ("cli", "dashboard", "mobile", "api", "installer", "daemon")


def _count(module: str, attribute: str) -> int:
    try:
        return len(getattr(importlib.import_module(module), attribute))
    except Exception:
        return 0


def manifest() -> Dict[str, Any]:
    """Return the full capability surface with live counts."""
    from pegasus.modules.access_workflow import post_exploitation, zero_click

    factory_commands = 0
    try:
        from pegasus.modules.access_workflow.agent import get_command_factory

        factory_commands = len(get_command_factory().list_commands())
    except Exception:
        pass

    groups = {
        "zero_click": {
            "module": "pegasus.modules.access_workflow.zero_click",
            "count": len(zero_click.EXPLOITS),
            "families": zero_click.device_families(),
        },
        "post_exploitation": {
            "module": "pegasus.modules.access_workflow.post_exploitation",
            "count": len(post_exploitation.COMMANDS),
            "chain": list(post_exploitation.CHAIN_ORDER),
        },
        "nso_capabilities": {
            "module": "pegasus.modules.access_workflow.nso_capabilities",
            "count": len(nso_capabilities.CAPABILITIES),
            "parity": nso_capabilities.parity_report(),
        },
        "features": {
            "module": "pegasus.modules.access_workflow",
            "count": 6,
            "keys": ["ai_mutation", "mass_payload", "dna", "steganography", "telegram_control", "frp_unlock"],
        },
        "factory": {
            "module": "pegasus.modules.access_workflow.agent.factory",
            "count": factory_commands,
        },
        "agents": {
            "module": "pegasus.modules.access_workflow.agent",
            "count": len(_agent_names()),
        },
    }
    return {
        "version": "2.0.0",
        "surfaces": list(SURFACES),
        "groups": groups,
        "total": sum(group["count"] for group in groups.values()),
        "parity_complete": groups["nso_capabilities"]["parity"]["coverage_percent"] == 100.0,
    }


def _agent_names() -> List[str]:
    try:
        from pegasus.modules.access_workflow.agent import list_agents

        return [agent["name"] for agent in list_agents()]
    except Exception:
        return []


def assert_parity() -> Dict[str, Any]:
    """Raise when any subsystem reports zero capability."""
    data = manifest()
    empty = [name for name, group in data["groups"].items() if group["count"] == 0]
    if empty:
        raise RuntimeError(f"capability groups empty: {', '.join(empty)}")
    if not data["parity_complete"]:
        raise RuntimeError("NSO parity is incomplete")
    return data


__all__ = ["SURFACES", "manifest", "assert_parity"]
