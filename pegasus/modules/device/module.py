"""
Pegasus Phantom Menace v2 - Device Module
Device management, ADB communication, fingerprinting, and inventory.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.panel import Panel

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import CommandInfo, UIComponent, hook, command, ui_component, HookType
from pegasus.core.config import get_settings


class DeviceModule(BaseModule):
    """Device management module - ADB communication, fingerprinting, inventory."""

    metadata = None  # Set by plugin loader

    @property
    def module_name(self) -> str:
        return "Device Management"

    @property
    def module_description(self) -> str:
        return "ADB device communication, fingerprinting, and inventory management"

    @property
    def module_category(self) -> str:
        return "device"

    async def _register_commands(self) -> None:
        self.register_command("devices", "List connected ADB devices", self.cmd_devices)
        self.register_command("device-info", "Get detailed device information", self.cmd_device_info)
        self.register_command("connect", "Connect to a device via ADB", self.cmd_connect)
        self.register_command("disconnect", "Disconnect a device", self.cmd_disconnect)
        self.register_command("shell", "Execute ADB shell command", self.cmd_shell)
        self.register_command("fingerprint", "Fingerprint device (Android version, patch level)", self.cmd_fingerprint)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="device_dashboard",
            component_type="panel",
            path="/devices",
            title="Device Dashboard",
            icon="📱",
            order=1,
        )

    async def _register_hooks(self) -> None:
        self.register_hook(HookType.DEVICE_CONNECTED, self._on_device_connected, priority=10)
        self.register_hook(HookType.DEVICE_DISCONNECTED, self._on_device_disconnected, priority=10)

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_devices(self, *args) -> None:
        """List all connected ADB devices."""
        self._console.print("[cyan]► Scanning for ADB devices...[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "adb", "devices", "-l",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            self.print_error(f"ADB error: {stderr.decode() if stderr else 'unknown'}")
            return

        lines = stdout.decode().strip().splitlines()
        if len(lines) <= 1:
            self.print_warning("No devices found")
            return

        table = Table(title="Connected ADB Devices", header_style="bold cyan")
        table.add_column("Serial", style="bold yellow")
        table.add_column("Status", style="green")
        table.add_column("Model", style="white")
        table.add_column("Transport", style="dim")

        for line in lines[1:]:
            if line.strip():
                parts = line.split()
                serial = parts[0]
                status = parts[1] if len(parts) > 1 else "device"
                model = "Unknown"
                transport = "usb"
                # Parse -l output for model
                for part in parts:
                    if part.startswith("model:"):
                        model = part.split(":", 1)[1]
                    if part.startswith("transport:"):
                        transport = part.split(":", 1)[1]
                table.add_row(serial, status, model, transport)

        self._console.print(table)

    async def cmd_device_info(self, *args) -> None:
        """Get detailed information about a device."""
        device_id = args[0] if args else self.get_device_id()
        if not device_id:
            self.print_error("No device specified. Use: pegasus device-info <serial>")
            return

        self._console.print(f"[cyan]► Gathering device info for {device_id}...[/cyan]")

        props = {
            "ro.product.model": "Model",
            "ro.product.manufacturer": "Manufacturer",
            "ro.build.version.release": "Android Version",
            "ro.build.version.sdk": "API Level",
            "ro.build.version.security_patch": "Security Patch",
            "ro.build.id": "Build ID",
            "ro.build.type": "Build Type",
            "ro.product.cpu.abi": "CPU ABI",
            "ro.product.name": "Product Name",
            "ro.serialno": "Serial Number",
        }

        rows = []
        for prop, label in props.items():
            proc = await asyncio.create_subprocess_exec(
                "adb", "-s", device_id, "shell", f"getprop {prop}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            value = stdout.decode().strip() if proc.returncode == 0 else "Unknown"
            rows.append([label, value])

        # Check root
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", device_id, "shell", "which su",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        rooted = "Yes (su found)" if proc.returncode == 0 else "No"

        rows.append(["Rooted", rooted])

        # Battery
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", device_id, "shell", "dumpsys battery | grep level",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        battery = stdout.decode().strip() if proc.returncode == 0 else "Unknown"
        rows.append(["Battery", battery])

        self.print_table(f"Device Info - {device_id}", ["Property", "Value"], rows)

    async def cmd_connect(self, *args) -> None:
        """Connect to a device via ADB."""
        target = args[0] if args else self.prompt("Device IP:Serial or serial")
        if not target:
            return

        self._console.print(f"[cyan]► Connecting to {target}...[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "adb", "connect", target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""

        if proc.returncode == 0 and "connected" in output.lower():
            self.print_success(f"Connected to {target}")
            await self.hooks.execute(HookType.DEVICE_CONNECTED, {
                "device": target,
                "method": "adb_connect",
            })
        else:
            self.print_error(f"Connection failed: {error or output}")

    async def cmd_disconnect(self, *args) -> None:
        """Disconnect a device."""
        target = args[0] if args else self.get_device_id()
        if not target:
            self.print_error("No device specified")
            return

        proc = await asyncio.create_subprocess_exec(
            "adb", "disconnect", target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        output = stdout.decode() if stdout else ""
        if proc.returncode == 0:
            self.print_success(f"Disconnected from {target}")
            await self.hooks.execute(HookType.DEVICE_DISCONNECTED, {"device": target})
        else:
            self.print_error(f"Disconnect failed: {stderr.decode() if stderr else output}")

    async def cmd_shell(self, *args) -> None:
        """Execute ADB shell command."""
        if not args:
            self.print_error("Usage: pegasus shell <command>")
            return

        device_id = self.get_device_id()
        cmd = " ".join(args)
        adb_cmd = ["adb"]
        if device_id:
            adb_cmd.extend(["-s", device_id])
        adb_cmd.extend(["shell", cmd])

        self._console.print(f"[dim]> {' '.join(adb_cmd)}[/dim]")

        proc = await asyncio.create_subprocess_exec(
            *adb_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if stdout:
            self._console.print(stdout.decode())
        if stderr:
            self._console.print(f"[red]{stderr.decode()}[/red]")

    async def cmd_fingerprint(self, *args) -> None:
        """Fingerprint device for CVE scanning."""
        device_id = args[0] if args else self.get_device_id()
        if not device_id:
            self.print_error("No device specified")
            return

        self._console.print(f"[cyan]► Fingerprinting {device_id}...[/cyan]")

        props = {
            "ro.build.version.release": "android_version",
            "ro.build.version.sdk": "api_level",
            "ro.build.version.security_patch": "security_patch",
            "ro.product.model": "model",
            "ro.product.manufacturer": "manufacturer",
        }

        info = {}
        for prop, key in props.items():
            proc = await asyncio.create_subprocess_exec(
                "adb", "-s", device_id, "shell", f"getprop {prop}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            info[key] = stdout.decode().strip() if proc.returncode == 0 else "Unknown"

        self.print_table(f"Device Fingerprint - {device_id}", ["Property", "Value"], [
            [k.replace("_", " ").title(), v] for k, v in info.items()
        ])

        # Store fingerprint in context for vulnerability scanning
        self.context.device_fingerprint = info

    # ── Hook Handlers ─────────────────────────────────────────────────

    async def _on_device_connected(self, context) -> None:
        """Handle device connected hook."""
        device = context.data.get("device", "unknown")
        self.print_info(f"Device connected: {device}")

    async def _on_device_disconnected(self, context) -> None:
        """Handle device disconnected hook."""
        device = context.data.get("device", "unknown")
        self.print_warning(f"Device disconnected: {device}")