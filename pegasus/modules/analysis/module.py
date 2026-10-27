"""
Pegasus Phantom Menace v2 - CVE Scanner Module
Android CVE fingerprinting, NVD lookup, and vulnerability scanning.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich import box

from pegasus_v2.modules.base import BaseModule
from pegasus_v2.core.plugin import CommandInfo, UIComponent, hook, command, ui_component, HookType
from pegasus_v2.core.config import get_settings


# Curated high-impact Android CVEs
BUILTIN_CVES = [
    {"id": "CVE-2024-31317", "description": "ZygoteProcess command injection — system-level code execution", "severity": "Critical", "cvss": 9.8, "affected_api_min": 30, "affected_api_max": 34, "patch_level": "2024-07-01"},
    {"id": "CVE-2024-0044", "description": "run-as privilege escalation via PackageManager race condition", "severity": "High", "cvss": 7.7, "affected_api_min": 31, "affected_api_max": 34, "patch_level": "2024-06-01"},
    {"id": "CVE-2023-21492", "description": "Kernel information disclosure via race condition", "severity": "High", "cvss": 7.4, "affected_api_min": 28, "affected_api_max": 33, "patch_level": "2023-05-01"},
    {"id": "CVE-2023-20963", "description": "WorkSource privilege escalation — allows app to run as system", "severity": "High", "cvss": 7.8, "affected_api_min": 30, "affected_api_max": 33, "patch_level": "2023-03-01"},
    {"id": "CVE-2022-20465", "description": "Lockscreen bypass — access device without PIN", "severity": "Critical", "cvss": 9.1, "affected_api_min": 30, "affected_api_max": 32, "patch_level": "2022-11-01"},
    {"id": "CVE-2022-20452", "description": "Permission bypass in NotificationManager leads to privilege escalation", "severity": "High", "cvss": 8.4, "affected_api_min": 30, "affected_api_max": 33, "patch_level": "2022-12-01"},
    {"id": "CVE-2021-39793", "description": "GPU driver heap OOB write — local privilege escalation", "severity": "Critical", "cvss": 8.8, "affected_api_min": 26, "affected_api_max": 32, "patch_level": "2022-03-05"},
    {"id": "CVE-2021-0954", "description": "Intent redirection in Android framework", "severity": "High", "cvss": 7.3, "affected_api_min": 26, "affected_api_max": 31, "patch_level": "2021-12-01"},
    {"id": "CVE-2020-0041", "description": "Binder OOB write — full root exploit chain available", "severity": "Critical", "cvss": 9.8, "affected_api_min": 26, "affected_api_max": 29, "patch_level": "2020-03-01"},
    {"id": "CVE-2019-2215", "description": "Use-after-free in Binder IPC driver — used in in-the-wild exploits", "severity": "Critical", "cvss": 9.3, "affected_api_min": 21, "affected_api_max": 28, "patch_level": "2019-10-06"},
    {"id": "CVE-2017-13156", "description": "Janus vulnerability — APK signature bypass allows code injection", "severity": "High", "cvss": 7.8, "affected_api_min": 21, "affected_api_max": 26, "patch_level": "2017-12-01"},
    {"id": "CVE-2015-3864", "description": "Stagefright — MMS media processing RCE", "severity": "Critical", "cvss": 10.0, "affected_api_min": 16, "affected_api_max": 22, "patch_level": "2015-09-01"},
]


class CVEScannerModule(BaseModule):
    """Android CVE Scanner module - vulnerability fingerprinting and NVD lookup."""

    @property
    def module_name(self) -> str:
        return "CVE Scanner"

    @property
    def module_description(self) -> str:
        return "Android CVE fingerprinting via ADB + NVD API lookup"

    @property
    def module_category(self) -> str:
        return "analysis"

    async def _register_commands(self) -> None:
        self.register_command("cve-scan", "Scan device for CVEs", self.cmd_cve_scan)
        self.register_command("cve-manual", "Manual CVE scan (version + patch)", self.cmd_cve_manual)
        self.register_command("cve-list", "List known CVEs", self.cmd_cve_list)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="cve_dashboard",
            component_type="panel",
            path="/cve",
            title="CVE Scanner",
            icon="🛡️",
            order=4,
        )

    async def _register_hooks(self) -> None:
        self.register_hook(HookType.VULN_SCAN_START, self._on_scan_start, priority=10)
        self.register_hook(HookType.VULN_SCAN_COMPLETE, self._on_scan_complete, priority=10)

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_cve_scan(self, *args) -> None:
        """Scan connected device for CVEs via ADB."""
        self._console.print("[cyan]► Fingerprinting device via ADB...[/cyan]")

        info = await self._get_device_info_adb()
        if not info:
            return

        api_level = int(info.get("api_level", "0") or "0")
        if api_level == 0:
            api_level = self._version_to_api(info.get("android_version", "0"))

        security_patch = info.get("security_patch", "1970-01-01")

        # Device fingerprint table
        table = Table(title="Device Fingerprint", show_lines=True)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="yellow")
        for k, v in info.items():
            table.add_row(k.replace("_", " ").title(), v)
        self._console.print(table)

        self._console.print(f"\n[cyan]► Checking against CVE database (API={api_level}, Patch={security_patch})...[/cyan]")

        vulns = [cve for cve in BUILTIN_CVES if self._is_vulnerable(cve, api_level, security_patch)]

        await self.hooks.execute(HookType.VULN_SCAN_COMPLETE, {
            "device": info,
            "api_level": api_level,
            "vulnerabilities": vulns,
        })

        if not vulns:
            self.print_success("No matching CVEs found for this device/patch level")
            return

        # Display results
        result_table = Table(
            title=f"[bold red]⚠  {len(vulns)} CVE(s) Found[/]",
            box=box.SIMPLE_HEAVY,
            show_lines=True,
        )
        result_table.add_column("CVE ID", style="bold yellow")
        result_table.add_column("Severity", style="red")
        result_table.add_column("CVSS", style="magenta")
        result_table.add_column("Description", style="white")
        result_table.add_column("Patch Date", style="dim")

        for v in sorted(vulns, key=lambda x: x.get("cvss", 0), reverse=True):
            sev = v.get("severity", "")
            sev_colored = (
                f"[bold red]{sev}[/]" if sev == "Critical"
                else f"[red]{sev}[/]" if sev == "High"
                else f"[yellow]{sev}[/]" if sev == "Medium"
                else f"[green]{sev}[/]"
            )
            result_table.add_row(
                v.get("id", ""),
                sev_colored,
                str(v.get("cvss", "")),
                v.get("description", "")[:70],
                v.get("patch_level", "NVD"),
            )

        self._console.print(result_table)

    async def cmd_cve_manual(self, *args) -> None:
        """Manual CVE scan - enter version and patch level."""
        ver = self.prompt("Android version (e.g. 12, 13, 14)")
        patch = self.prompt("Security patch level (YYYY-MM-DD)", default="2022-01-01")

        api_level = self._version_to_api(ver)
        self._console.print(f"[dim]  API level inferred: {api_level}[/dim]")

        vulns = [cve for cve in BUILTIN_CVES if self._is_vulnerable(cve, api_level, patch)]

        if not vulns:
            self.print_success("No matching CVEs found")
            return

        for v in sorted(vulns, key=lambda x: x.get("cvss", 0), reverse=True):
            self._console.print(
                f"  [bold yellow]{v['id']}[/]  CVSS {v['cvss']}  "
                f"[red]{v['severity']}[/]  {v['description'][:60]}"
            )

    async def cmd_cve_list(self, *args) -> None:
        """List all known CVEs in database."""
        table = Table(title="Known CVE Database", header_style="bold cyan")
        table.add_column("CVE ID", style="bold yellow")
        table.add_column("Severity", style="red")
        table.add_column("CVSS", style="magenta")
        table.add_column("Description", style="white")
        table.add_column("Patch Level", style="dim")
        table.add_column("Affected API", style="dim")

        for cve in sorted(BUILTIN_CVES, key=lambda x: x.get("cvss", 0), reverse=True):
            table.add_row(
                cve.get("id", ""),
                cve.get("severity", ""),
                str(cve.get("cvss", "")),
                cve.get("description", "")[:60],
                cve.get("patch_level", ""),
                f"{cve.get('affected_api_min', '?')}-{cve.get('affected_api_max', '?')}",
            )

        self._console.print(table)

    # ── Helpers ───────────────────────────────────────────────────────

    async def _get_device_info_adb(self) -> Optional[Dict[str, str]]:
        """Get device info via ADB."""
        proc = await asyncio.create_subprocess_exec(
            "adb", "shell", "getprop",
            "ro.build.version.release",
            "ro.build.version.sdk",
            "ro.build.version.security_patch",
            "ro.product.model",
            "ro.product.manufacturer",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            self.print_error("ADB not available or no device connected")
            return None

        output = stdout.decode()
        info = {}
        for line in output.strip().splitlines():
            if "[" in line and "]" in line:
                key = line.split("[")[1].split("]")[0]
                value = line.split("]: [")[1].rstrip("]") if "]: [" in line else ""
                info[key] = value

        return info

    def _version_to_api(self, v: str) -> int:
        mapping = {"15":35,"14":34,"13":33,"12":31,"11":30,"10":29,"9":28,"8":27,"7":24,"6":23,"5":21}
        for k, api in mapping.items():
            if v.startswith(k):
                return api
        try:
            return int(v.split(".")[0]) + 20
        except:
            return 0

    def _patch_to_tuple(self, p: str) -> tuple:
        try:
            parts = p.split("-")
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except:
            return (0, 0, 0)

    def _is_vulnerable(self, cve: Dict, api_level: int, security_patch: str) -> bool:
        affects = cve.get("affected", {})
        min_api = affects.get("min_api", 0)
        max_api = affects.get("max_api", 99)
        if not (min_api <= api_level <= max_api):
            return False
        patch_date = self._patch_to_tuple(security_patch)
        fix_date = self._patch_to_tuple(cve.get("patch_level", "9999-12-01"))
        return patch_date < fix_date

    # ── Hook Handlers ─────────────────────────────────────────────────

    async def _on_scan_start(self, context) -> None:
        self._console.print("[cyan]► CVE scan started[/cyan]")

    async def _on_scan_complete(self, context) -> None:
        vulns = context.data.get("vulnerabilities", [])
        self.print_info(f"Scan complete: {len(vulns)} vulnerabilities found")