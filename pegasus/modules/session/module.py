"""
Pegasus Phantom Menace v2 - Session Module
Metasploit RPC session management, keepalive, device operations.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel

from pegasus_v2.modules.base import BaseModule
from pegasus_v2.core.plugin import CommandInfo, UIComponent, hook, command, ui_component, HookType


class SessionModule(BaseModule):
    """Session management module - Metasploit RPC, keepalive, device ops."""

    @property
    def module_name(self) -> str:
        return "Session Manager"

    @property
    def module_description(self) -> str:
        return "Metasploit RPC integration, session keepalive, and device operations"

    @property
    def module_category(self) -> str:
        return "session"

    async def _register_commands(self) -> None:
        self.register_command("sessions", "List active Meterpreter sessions", self.cmd_sessions)
        self.register_command("session-info", "Get detailed session information", self.cmd_session_info)
        self.register_command("session-command", "Execute command in session", self.cmd_session_command)
        self.register_command("keepalive", "Manage session keepalive", self.cmd_keepalive)
        self.register_command("auto-fetch", "Auto-fetch new sessions", self.cmd_auto_fetch)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="session_dashboard",
            component_type="panel",
            path="/sessions",
            title="Session Dashboard",
            icon="📡",
            order=3,
        )

    async def _register_hooks(self) -> None:
        self.register_hook(HookType.SESSION_CREATED, self._on_session_created, priority=10)

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_sessions(self, *args) -> None:
        """List active sessions."""
        self._console.print("[cyan]► Fetching sessions from Metasploit RPC...[/cyan]")

        # Try to connect to Metasploit RPC
        sessions = await self._rpc_list_sessions()

        if not sessions:
            self.print_warning("No active sessions or RPC not available")
            self._console.print("[dim]Start Metasploit RPC: start-msfrpc <password> <port>[/dim]")
            return

        table = Table(title="Active Meterpreter Sessions", header_style="bold cyan")
        table.add_column("SID", style="bold yellow")
        table.add_column("Type", style="cyan")
        table.add_column("Tunnel", style="white")
        table.add_column("Uptime", style="green")
        table.add_column("Keepalive", style="dim")

        for sid, info in sessions.items():
            table.add_row(
                str(sid),
                info.get("type", "unknown"),
                info.get("tunnel", "direct"),
                info.get("uptime", "0:00:00"),
                "● Active" if info.get("keepalive") else "○ Off",
            )

        self._console.print(table)

    async def cmd_session_info(self, *args) -> None:
        """Get detailed session information."""
        sid = args[0] if args else self.prompt("Session ID")
        if not sid:
            return

        self._console.print(f"[cyan]► Getting info for session {sid}...[/cyan]")

        info = await self._rpc_session_info(sid)
        if not info:
            self.print_error("Session not found or RPC unavailable")
            return

        rows = [
            ["Session ID", sid],
            ["Type", info.get("type", "unknown")],
            ["Tunnel", info.get("tunnel", "direct")],
            ["Platform", info.get("platform", "unknown")],
            ["UUID", info.get("uuid", "unknown")],
            ["Username", info.get("username", "unknown")],
            ["Hostname", info.get("hostname", "unknown")],
            ["Uptime", info.get("uptime", "0:00:00")],
        ]

        self.print_table(f"Session Info - {sid}", ["Property", "Value"], rows)

    async def cmd_session_command(self, *args) -> None:
        """Execute command in a session."""
        if len(args) < 2:
            self.print_error("Usage: pegasus session-command <sid> <command>")
            return

        sid, cmd = args[0], " ".join(args[1:])
        self._console.print(f"[dim]> session {sid} > {cmd}[/dim]")

        output = await self._rpc_session_command(sid, cmd)
        if output:
            self._console.print(output)
        else:
            self.print_warning("No output or command failed")

    async def cmd_keepalive(self, *args) -> None:
        """Manage session keepalive."""
        sid = args[0] if args else self.prompt("Session ID")
        if not sid:
            return

        interval = self.prompt_int("Keepalive interval (seconds)", default=60)

        self._console.print(f"[cyan]► Starting keepalive for session {sid} (interval: {interval}s)...[/cyan]")
        success = await self._rpc_start_keepalive(sid, interval)

        if success:
            self.print_success(f"Keepalive started for session {sid}")
        else:
            self.print_error("Failed to start keepalive")

    async def cmd_auto_fetch(self, *args) -> None:
        """Auto-fetch new sessions."""
        interval = self.prompt_int("Poll interval (seconds)", default=5)
        duration = self.prompt_int("Watch duration (seconds)", default=600)

        self._console.print(f"[cyan]► Auto-fetching sessions every {interval}s for {duration}s...[/cyan]")
        self._console.print("[dim]Press Ctrl+C to stop[/dim]")

        import time as time_mod
        start = time_mod.time()
        seen_sids = set()

        try:
            while (time_mod.time() - start) < duration:
                sessions = await self._rpc_list_sessions()
                new_sids = set(sessions.keys()) - seen_sids

                for sid in new_sids:
                    self.print_success(f"New session detected: {sid}")
                    info = sessions.get(sid, {})
                    await self._rpc_start_keepalive(sid, 60)
                    seen_sids.add(sid)

                seen_sids = set(sessions.keys())
                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            self.print_warning("Auto-fetch stopped")

    # ── RPC Helpers ───────────────────────────────────────────────────

    async def _rpc_list_sessions(self) -> Dict[str, Any]:
        """List sessions via Metasploit RPC."""
        # Try to import pymetasploit3
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
        except ImportError:
            self.print_warning("pymetasploit3 not installed. Run: pip install pymetasploit3")
            return {}

        settings = self.context.settings
        try:
            client = MsfRpcClient(
                settings.metasploit.rpc_password,
                server=settings.metasploit.rpc_host,
                port=settings.metasploit.rpc_port,
                ssl=settings.metasploit.rpc_ssl,
            )
            sessions = client.sessions.list
            return sessions
        except Exception as e:
            self.print_warning(f"RPC connection failed: {e}")
            return {}

    async def _rpc_session_info(self, sid: str) -> Optional[Dict[str, Any]]:
        """Get session info via RPC."""
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
        except ImportError:
            return None

        settings = self.context.settings
        try:
            client = MsfRpcClient(
                settings.metasploit.rpc_password,
                server=settings.metasploit.rpc_host,
                port=settings.metasploit.rpc_port,
                ssl=settings.metasploit.rpc_ssl,
            )
            session = client.sessions.session(sid)
            info = session.info
            return info if isinstance(info, dict) else {}
        except Exception:
            return None

    async def _rpc_session_command(self, sid: str, command: str) -> Optional[str]:
        """Execute command in session via RPC."""
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
        except ImportError:
            return None

        settings = self.context.settings
        try:
            client = MsfRpcClient(
                settings.metasploit.rpc_password,
                server=settings.metasploit.rpc_host,
                port=settings.metasploit.rpc_port,
                ssl=settings.metasploit.rpc_ssl,
            )
            session = client.sessions.session(sid)
            output = session.run_with_output(command)
            return output
        except Exception as e:
            self.print_error(f"Command failed: {e}")
            return None

    async def _rpc_start_keepalive(self, sid: str, interval: int) -> bool:
        """Start keepalive for a session."""
        try:
            from pymetasploit3.msfrpc import MsfRpcClient
        except ImportError:
            return False

        settings = self.context.settings
        try:
            client = MsfRpcClient(
                settings.metasploit.rpc_password,
                server=settings.metasploit.rpc_host,
                port=settings.metasploit.rpc_port,
                ssl=settings.metasploit.rpc_ssl,
            )
            session = client.sessions.session(sid)
            session.run_with_output(f"sleep {interval}; getuid")
            return True
        except Exception:
            return False

    def prompt_int(self, message: str, default: int = 0) -> int:
        """Prompt for an integer."""
        while True:
            val = self.prompt(message, default=str(default))
            try:
                return int(val)
            except ValueError:
                self.print_error("Please enter a valid integer")

    # ── Hook Handlers ─────────────────────────────────────────────────

    async def _on_session_created(self, context) -> None:
        """Handle session created hook."""
        sid = context.data.get("sid", "unknown")
        self.print_success(f"New session: {sid}")