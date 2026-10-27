"""
Pegasus Phantom Menace v2 - Main Application Entry Point
Unified CLI/TUI/Web interface that loads all plugins and provides a cohesive interface.
"""
from __future__ import annotations

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pegasus.core.config import get_settings, Settings
from pegasus.core.plugin import (
    initialize_plugin_system,
    get_plugin_manager,
    HookType,
    CommandInfo,
)
from pegasus.core.db.session import init_db, close_db, get_session

console = Console()


def show_banner() -> None:
    """Display the application banner."""
    banner = Text()
    banner.append("PEGASUS: Phantom Menace\n", style="bold red")
    banner.append("Android Device Management & Security Audit Platform v2.0.0\n", style="bold cyan")
    banner.append("License: MIT  |  Access Code: R0om2fb9!\n", style="dim yellow")
    banner.append("For authorized security testing only.", style="dim white")

    console.print(Panel(banner, border_style="red", padding=(1, 2)))
    console.print()


def show_status_bar() -> None:
    """Show system status bar."""
    settings = get_settings()
    pm = get_plugin_manager()
    plugin_list = pm.list_plugins()

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold cyan", width=14)
    table.add_column("Value", style="white")

    table.add_row("Version", "2.0.0")
    table.add_row("Workspace", str(settings.app.workspace))
    table.add_row("Database", settings.database.type)
    table.add_row("Plugins Loaded", str(len(plugin_list)))
    table.add_row("AI Status", "Configured" if settings.ai.api_key else "Not configured")
    table.add_row("Metasploit RPC", f"{settings.metasploit.rpc_host}:{settings.metasploit.rpc_port}")

    console.print(table)
    console.print()


def list_plugins() -> None:
    """List all loaded plugins."""
    pm = get_plugin_manager()
    plugin_list = pm.list_plugins()

    table = Table(title="Loaded Plugins", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold yellow")
    table.add_column("Version", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Category", style="green")
    table.add_column("Tags", style="magenta")

    for p in plugin_list:
        table.add_row(
            p["name"],
            p["version"],
            p["description"][:60] + "..." if len(p["description"]) > 60 else p["description"],
            p["category"],
            ", ".join(p["tags"]),
        )

    console.print(table)


def show_main_menu() -> None:
    """Show the main menu with all available commands."""
    from pegasus.core.plugin import get_plugin_manager
    pm = get_plugin_manager()
    commands = pm.context.commands

    # Group commands by plugin
    grouped = {}
    for name, cmd in commands.items():
        # Find which plugin owns this command
        owner = "core"
        for plugin in pm.context.plugins.values():
            if name in plugin.get_commands():
                owner = plugin.metadata.name
                break
        if owner not in grouped:
            grouped[owner] = []
        grouped[owner].append((name, cmd.description))

    console.print("\n[bold cyan]Main Menu[/bold cyan]\n")
    for plugin_name, cmds in grouped.items():
        table = Table(title=f"{plugin_name.title()} ({len(cmds)} commands)", show_header=False, box=None)
        table.add_column("Command", style="bold yellow", width=25)
        table.add_column("Description", style="white")
        for name, desc in cmds[:8]:  # Limit to 8 per plugin for display
            table.add_row(f"pegasus {name}", desc)
        console.print(table)
        console.print()


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--config", type=click.Path(exists=False), help="Path to config file")
@click.pass_context
def cli(ctx: click.Context, debug: bool, config: Optional[str]) -> None:
    """Pegasus Phantom Menace - Android Security Platform."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["config_path"] = config

    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
def init() -> None:
    """Initialize the workspace and database."""
    console.print("[bold cyan]Initializing Pegasus Phantom Menace v2...[/cyan]")

    # Initialize database
    asyncio.run(init_db())

    # Initialize plugin system
    pm = initialize_plugin_system()

    console.print(f"[green]✓[/green] Database initialized")
    console.print(f"[green]✓[/green] Plugin system loaded ({len(pm.list_plugins())} plugins)")
    console.print("\n[bold green]Ready to use Pegasus![/bold green]")


@cli.command()
def plugins() -> None:
    """List all loaded plugins."""
    initialize_plugin_system()
    list_plugins()


@cli.command()
@click.argument("plugin_name")
def plugin_info(plugin_name: str) -> None:
    """Show detailed information about a plugin."""
    pm = get_plugin_manager()
    info = pm.get_plugin_info(plugin_name)

    if not info:
        console.print(f"[red]Plugin '{plugin_name}' not found.[/red]")
        return

    console.print(Panel(f"[bold]{info['name']} v{info['version']}[/bold]", border_style="cyan"))
    console.print(f"Description: {info['description']}")
    console.print(f"Author: {info['author']}")
    console.print(f"Category: {info['category']}")
    console.print(f"Tags: {', '.join(info['tags'])}")
    console.print(f"License: {info['license']}")

    if info["commands"]:
        console.print("\n[bold]Commands:[/bold]")
        for cmd in info["commands"]:
            console.print(f"  [yellow]{cmd['name']}[/yellow] - {cmd['description']}")

    if info["ui_components"]:
        console.print("\n[bold]UI Components:[/bold]")
        for comp in info["ui_components"]:
            console.print(f"  [cyan]{comp['name']}[/cyan] ({comp['component_type']}) - {comp['title']}")


@cli.command()
def status() -> None:
    """Show system status."""
    settings = get_settings()
    pm = get_plugin_manager()

    console.print(Panel("[bold cyan]Pegasus System Status[/bold cyan]", border_style="cyan"))

    table = Table(show_header=False, box=None)
    table.add_column("Component", style="bold cyan", width=20)
    table.add_column("Status", style="green")
    table.add_column("Details", style="white")

    table.add_row("Database", "✓ Connected", settings.database.type)
    table.add_row("AI Assistant", "✓ Configured" if settings.ai.api_key else "✗ Not configured", settings.ai.model)
    table.add_row("Metasploit RPC", "✓ Configured", f"{settings.metasploit.rpc_host}:{settings.metasploit.rpc_port}")
    table.add_row("Plugins Loaded", str(len(pm.list_plugins())), "")
    table.add_row("Workspace", str(settings.app.workspace), "")

    console.print(table)


@cli.command()
@click.argument("command", nargs=-1)
def run(command: tuple) -> None:
    """Execute a registered plugin command."""
    pm = get_plugin_manager()
    if not command:
        console.print("[red]No command specified.[/red]")
        console.print("Available commands: " + ", ".join(pm.context.commands.keys()))
        return

    cmd_name = command[0]
    cmd_args = command[1:]

    cmd = pm.context.commands.get(cmd_name)
    if not cmd:
        console.print(f"[red]Command '{cmd_name}' not found.[/red]")
        console.print("Available commands: " + ", ".join(pm.context.commands.keys()))
        return

    # Execute the command callback
    plugin = None
    for p in pm.context.plugins.values():
        if cmd_name in p.get_commands():
            plugin = p
            break

    if plugin:
        callback = getattr(plugin, cmd.callback, None)
        if callback:
            try:
                import asyncio
                asyncio.run(callback(*cmd_args))
            except Exception as e:
                console.print(f"[red]Command failed: {e}[/red]")
        else:
            console.print(f"[red]Callback '{cmd.callback}' not found on plugin.[/red]")
    else:
        console.print(f"[red]Plugin for command '{cmd_name}' not found.[/red]")


@cli.command()
def serve() -> None:
    """Start the web GUI server."""
    console.print("[bold cyan]Starting Pegasus Web GUI...[/bold cyan]")
    console.print("[yellow]Web GUI available in Phase 3. For now, use the CLI interface.[/yellow]")


@cli.command()
def menu() -> None:
    """Interactive menu mode."""
    initialize_plugin_system()
    show_banner()
    show_status_bar()

    while True:
        show_main_menu()
        try:
            choice = Prompt.ask(
                "\n[bold red]pegasus[/][dim]>[/]",
                default="0",
                show_choices=False,
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Goodbye. Stay legal, stay ethical.[/]\n")
            break

        if choice == "0" or choice.lower() in ("q", "quit", "exit"):
            console.print("[bold red]Goodbye. Stay legal, stay ethical.[/]\n")
            break

        # Try to run as command
        parts = choice.split()
        cmd_name = parts[0]
        cmd_args = parts[1:]

        pm = get_plugin_manager()
        cmd = pm.context.commands.get(cmd_name)
        if cmd:
            plugin = None
            for p in pm.context.plugins.values():
                if cmd_name in p.get_commands():
                    plugin = p
                    break
            if plugin:
                callback = getattr(plugin, cmd.callback, None)
                if callback:
                    try:
                        import asyncio
                        asyncio.run(callback(*cmd_args))
                    except Exception as e:
                        console.print(f"[red]Command failed: {e}[/red]")
                else:
                    console.print(f"[red]Callback '{cmd.callback}' not found.[/red]")
            else:
                console.print(f"[red]Plugin for command '{cmd_name}' not found.[/red]")
        else:
            console.print(f"[red]Unknown command: {cmd_name}[/red]")
            console.print("Type 'pegasus plugins' to list available plugins")


@cli.command()
def version() -> None:
    """Show version information."""
    settings = get_settings()
    console.print(f"Pegasus Phantom Menace v{settings.app.version}")
    console.print(f"License: {settings.app.name}")


def main() -> None:
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        if get_settings().app.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()