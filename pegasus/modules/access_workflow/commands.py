"""
Pegasus Phantom Menace v2 - Access Workflow Command Registration

Registers the zero-click exploit suite (and later the post-exploitation,
feature and agent command families) on the shared slash-command manager.

Registration is idempotent: calling :func:`register` twice is a no-op, so the
CLI can call it on every startup without duplicating commands.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

console = Console()


def _free(scm: Any, name: str) -> bool:
    """Return True when a command name is not already registered."""
    try:
        return scm.get_command(name) is None
    except Exception:
        return name not in getattr(scm, "commands", {})


# ---------------------------------------------------------------------------
# Zero-click exploits
# ---------------------------------------------------------------------------


async def cmd_zeroclick_list(*args: str) -> List[Dict[str, Any]]:
    """List every zero-click exploit, optionally filtered."""
    from pegasus.modules.access_workflow import zero_click

    family = None
    transport = None
    for index, arg in enumerate(args):
        if arg in ("--family", "-f") and index + 1 < len(args):
            family = args[index + 1]
        if arg in ("--transport", "-t") and index + 1 < len(args):
            transport = args[index + 1]

    exploits = zero_click.list_exploits(device_family=family, transport=transport)
    table = Table(title="Zero-Click Exploit Registry")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Family")
    table.add_column("Transport")
    table.add_column("CVE / Surface")
    table.add_column("Description", overflow="fold")
    for exploit in exploits:
        table.add_row(
            exploit["key"],
            exploit["device_family"],
            exploit["transport"],
            exploit["cve"],
            exploit["description"],
        )
    console.print(table)
    console.print(f"[dim]{len(exploits)} vector(s). Run one with: /zeroclick-run <key>[/dim]")
    return exploits


async def cmd_zeroclick_run(*args: str) -> Dict[str, Any]:
    """Execute a single zero-click exploit by registry key."""
    from pegasus.modules.access_workflow import zero_click

    if not args:
        console.print("[red]Usage: /zeroclick-run <key> [kw=value ...][/red]")
        console.print("[dim]Discover keys with /zeroclick-list[/dim]")
        return {}
    key = args[0]
    kwargs: Dict[str, Any] = {}
    for arg in args[1:]:
        if "=" in arg:
            name, value = arg.split("=", 1)
            kwargs[name.replace("-", "_")] = value
    console.print(f"[cyan]Running zero-click vector:[/] {key}")
    try:
        result = zero_click.run_exploit(key, **kwargs)
    except Exception as exc:
        console.print(f"[red]Exploit failed:[/] {exc}")
        return {"exploit": key, "status": "error", "error": str(exc)}
    console.print_json(data=result)
    return result


async def cmd_zeroclick_sweep(*args: str) -> List[Dict[str, Any]]:
    """Run every vector for a device family (default: all families)."""
    from pegasus.modules.access_workflow import zero_click

    family = args[0] if args else None
    console.print(f"[cyan]Sweeping zero-click vectors[/] ({family or 'all families'})")
    results = zero_click.run_all(device_family=family)
    ok = sum(1 for item in results if item.get("status") != "error")
    console.print(f"[green]{ok}/{len(results)} vectors completed without error.[/green]")
    return results


def register(scm: Any) -> None:
    """Register workflow commands on a slash-command manager."""
    _register_zero_click(scm)
    _register_post_exploitation(scm)


def _register_zero_click(scm: Any) -> None:
    if _free(scm, "/zeroclick-list"):
        scm.register(
            "/zeroclick-list",
            "List zero-click exploit vectors (optionally --family/--transport)",
            cmd_zeroclick_list,
            category="exploit",
            examples=["/zeroclick-list", "/zeroclick-list --family pixel8"],
        )
    if _free(scm, "/zeroclick-run"):
        scm.register(
            "/zeroclick-run",
            "Run a zero-click exploit by registry key",
            cmd_zeroclick_run,
            category="exploit",
            examples=["/zeroclick-run android_bluetooth"],
        )
    if _free(scm, "/zeroclick-sweep"):
        scm.register(
            "/zeroclick-sweep",
            "Run every zero-click vector for a family",
            cmd_zeroclick_sweep,
            category="exploit",
            examples=["/zeroclick-sweep pixel8"],
        )


# ---------------------------------------------------------------------------
# Post-exploitation
# ---------------------------------------------------------------------------


async def cmd_postexploit_list(*args: str) -> List[Dict[str, Any]]:
    """List the post-exploitation chain in execution order."""
    from pegasus.modules.access_workflow.post_exploitation import registry

    steps = registry.list_commands()
    table = Table(title="Post-Exploitation Steps")
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Step", style="bold")
    table.add_column("Description", overflow="fold")
    for step in steps:
        table.add_row(str(step["position"] or "-"), step["key"], step["description"])
    console.print(table)
    return steps


async def cmd_postexploit_run(*args: str) -> Dict[str, Any]:
    """Run one post-exploitation step."""
    from pegasus.modules.access_workflow.post_exploitation import registry

    if not args:
        console.print("[red]Usage: /postexploit-run <step>[/red]")
        return {}
    try:
        result = await registry.run(args[0])
    except Exception as exc:
        console.print(f"[red]Step failed:[/] {exc}")
        return {"step": args[0], "status": "error", "error": str(exc)}
    console.print_json(data=result)
    return result


async def cmd_postexploit_chain(*args: str) -> List[Dict[str, Any]]:
    """Run the whole post-exploitation chain."""
    from pegasus.modules.access_workflow.post_exploitation import registry

    console.print("[cyan]Running full post-exploitation chain...[/cyan]")
    results = await registry.run_chain()
    failed = [item for item in results if item.get("status") == "error"]
    if failed:
        console.print(f"[red]Chain stopped at:[/] {failed[0]['step']}")
    else:
        console.print(f"[green]Chain completed:[/] {len(results)} steps")
    return results


def _register_post_exploitation(scm: Any) -> None:
    if _free(scm, "/postexploit-list"):
        scm.register(
            "/postexploit-list",
            "List post-exploitation steps",
            cmd_postexploit_list,
            category="exploit",
        )
    if _free(scm, "/postexploit-run"):
        scm.register(
            "/postexploit-run",
            "Run one post-exploitation step",
            cmd_postexploit_run,
            category="exploit",
            examples=["/postexploit-run fingerprint"],
        )
    if _free(scm, "/postexploit-chain"):
        scm.register(
            "/postexploit-chain",
            "Run the full post-exploitation chain",
            cmd_postexploit_chain,
            category="exploit",
        )
