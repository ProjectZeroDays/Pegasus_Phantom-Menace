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
from pegasus.modules.integrations import slash_command_manager, initialize_slash_commands

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


def _get_scm() -> SlashCommandManager:
    """Get or initialize slash command manager."""
    from pegasus.modules.integrations import slash_command_manager as _scm_mod
    global slash_command_manager
    if slash_command_manager is None:
        pm = get_plugin_manager()
        scm = initialize_slash_commands(pm.context)
        slash_command_manager = scm
    else:
        scm = slash_command_manager
    return scm


@cli.group()
def slash() -> None:
    """Slash commands - Pegasus high-level commands."""
    pass
    """Get or initialize slash command manager."""
    global slash_command_manager
    if slash_command_manager is None:
        pm = get_plugin_manager()
        scm = initialize_slash_commands(pm.context)
    else:
        scm = slash_command_manager
    return scm


@slash.command("slash-help")
def slash_help() -> None:
    """Show all available slash commands."""
    scm = _get_scm()
    scm.show_help()


@slash.command("adb-devices")
def slash_adb_devices() -> None:
    """List connected ADB devices."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("adb-devices"))


@slash.command("fastboot-devices")
def slash_fastboot_devices() -> None:
    """List fastboot devices."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("fastboot-devices"))


@slash.command("wireless-adb")
def slash_wireless_adb() -> None:
    """Wireless ADB connect with QR code and zeroclick bypass."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("wireless-adb"))


@slash.command("troubleshoot")
def slash_troubleshoot() -> None:
    """AI-powered runtime issue detection and debugging."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("troubleshoot"))


@slash.command("test")
def slash_test() -> None:
    """Run exhaustive test scripts."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("test"))


@slash.command("netscan")
def slash_netscan() -> None:
    """Network device and service discovery."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("netscan"))


@slash.command("btscan")
def slash_btscan() -> None:
    """Bluetooth proximity scanning."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("btscan"))


@slash.command("wifiscan")
def slash_wifiscan() -> None:
    """WiFi beacon scanning."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("wifiscan"))


@slash.command("nmap-scan")
def slash_nmap_scan() -> None:
    """Comprehensive nmap network scan with PDF report."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("nmap-scan"))


@slash.command("tshark")
def slash_tshark() -> None:
    """TShark packet capture and analysis."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("tshark"))


@slash.command("wireshark")
def slash_wireshark() -> None:
    """Wireshark packet capture and analysis."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("wireshark"))


@slash.command("frp-bypass")
def slash_frp_bypass() -> None:
    """FRP bypass for Android devices."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("frp-bypass"))


@slash.command("exploit")
def slash_exploit() -> None:
    """General exploitation framework."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("exploit"))


@slash.command("post-exploitation")
def slash_post_exploitation() -> None:
    """Post-exploitation automation."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("post-exploitation"))


@slash.command("generate-payload")
def slash_generate_payload() -> None:
    """Generate exploitation payloads."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("generate-payload"))


@slash.command("audit-security")
def slash_audit_security() -> None:
    """Security audit."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("audit-security"))


@slash.command("harden-app")
def slash_harden_app() -> None:
    """Harden application."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("harden-app"))


@slash.command("harden-device")
def slash_harden_device() -> None:
    """Harden device."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("harden-device"))


@slash.command("kill-switch")
def slash_kill_switch() -> None:
    """Kill switch activation."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("kill-switch"))


@slash.command("dump-credentials")
def slash_dump_credentials() -> None:
    """Dump credentials from device."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("dump-credentials"))


@slash.command("crack-hashes")
def slash_crack_hashes() -> None:
    """Cryptographic hash cracking."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("crack-hashes"))


@slash.command("crack-passwords")
def slash_crack_passwords() -> None:
    """Password cracking."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("crack-passwords"))


@slash.command("brute-force")
def slash_brute_force() -> None:
    """Brute force attacks."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("brute-force"))


@slash.command("create-rat-agent")
def slash_create_rat_agent() -> None:
    """Create RAT agent."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-rat-agent"))


@slash.command("create-exploit")
def slash_create_exploit() -> None:
    """Create custom exploits."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-exploit"))


@slash.command("wipe-logs")
def slash_wipe_logs() -> None:
    """Wipe system logs."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("wipe-logs"))


@slash.command("edit-logs")
def slash_edit_logs() -> None:
    """Edit system logs."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("edit-logs"))


@slash.command("create-exe")
def slash_create_exe() -> None:
    """Create Windows EXE."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-exe"))


@slash.command("create-ipa")
def slash_create_ipa() -> None:
    """Create iOS IPA."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-ipa"))


@slash.command("create-deb")
def slash_create_deb() -> None:
    """Create Debian DEB."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-deb"))


@slash.command("create-dmg")
def slash_create_dmg() -> None:
    """Create macOS DMG."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-dmg"))


@slash.command("create-apk")
def slash_create_apk() -> None:
    """Create Android APK."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-apk"))


@slash.command("create-flatpack")
def slash_create_flatpack() -> None:
    """Create Linux Flatpak."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-flatpack"))


@slash.command("create-snap")
def slash_create_snap() -> None:
    """Create Linux Snap."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-snap"))


@slash.command("zip")
def slash_create_zip() -> None:
    """Create ZIP archive."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("zip"))


@slash.command("tar")
def slash_create_tar() -> None:
    """Create TAR archive."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("tar"))


@slash.command("rar")
def slash_create_rar() -> None:
    """Create RAR archive."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("rar"))


@slash.command("create-vault")
def slash_create_vault() -> None:
    """Create encrypted vault."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("create-vault"))


@slash.command("open-vault")
def slash_open_vault() -> None:
    """Open encrypted vault."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("open-vault"))


@slash.command("crack-vault")
def slash_crack_vault() -> None:
    """Crack encrypted vault."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("crack-vault"))


@slash.command("docs")
def slash_docs() -> None:
    """Update all documentation including GitHub Wiki."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("docs"))


@slash.command("improve")
def slash_improve() -> None:
    """Continuous improvement and refactoring."""
    scm = _get_scm()
    import asyncio
    asyncio.run(scm.execute("improve"))


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