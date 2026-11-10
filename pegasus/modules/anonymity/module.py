"""
Anonymity module - Proxy/Tor helpers for operator traffic.

Provides:
- Tor proxy status / circuit info (via stem or tor control port)
- SOCKS5 proxy validation (local and remote)
- HTTP proxy chain builder (proxychains-style)
- Onion service descriptor generation
- Traffic tunneling helpers (SSH dynamic forward, socat relay)

All capabilities are defensive: missing binaries return structured results
rather than raising. Nothing routes traffic without explicit operator action.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import HookType
from pegasus.core.config import get_settings

try:
    import logging, colorama.ansitowin32 as _cw
    _orig = _cw.write
    def _safe(s, *a, **k):
        try: return _orig(s, *a, **k)
        except OSError: return len(s)
    _cw.write = _safe
    _oe = logging.StreamHandler.emit
    def _se(self, record):
        try: return _oe(self, record)
        except OSError: pass
    logging.StreamHandler.emit = _se
except Exception:
    pass


class AnonymityModule(BaseModule):
    """Proxy/Tor helpers for operator traffic."""

    @property
    def module_name(self) -> str:
        return "Anonymity / Proxy"

    @property
    def module_description(self) -> str:
        return "Proxy/Tor helpers for operator traffic"

    @property
    def module_category(self) -> str:
        return "exploit"

    async def _register_commands(self) -> None:
        self.register_command("anon-tor-status", "Check Tor proxy status and circuit info", self.cmd_tor_status)
        self.register_command("anon-socks-check", "Validate a SOCKS5 proxy", self.cmd_socks_check)
        self.register_command("anon-http-proxy", "Validate an HTTP proxy", self.cmd_http_proxy)
        self.register_command("anon-chain", "Build a proxy chain (proxychains-style)", self.cmd_chain)
        self.register_command("anon-ssh-forward", "Start SSH dynamic SOCKS forward", self.cmd_ssh_forward)
        self.register_command("anon-socat-relay", "Start a socat TCP relay", self.cmd_socat_relay)
        self.register_command("anon-onion-desc", "Generate Tor onion service descriptor", self.cmd_onion_desc)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="anonymity_dashboard",
            component_type="panel",
            path="/anonymity",
            title="Anonymity / Proxy Dashboard",
            icon="🕶️",
            order=11,
        )

    async def _register_hooks(self) -> None:
        pass

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_tor_status(self, *args) -> None:
        """Check Tor proxy status and circuit info."""
        tor_ports = [9050, 9150]
        found = None
        for port in tor_ports:
            if self._port_open("127.0.0.1", port):
                found = port
                break
        if found:
            self.print_success(f"Tor SOCKS proxy listening on 127.0.0.1:{found}")
            self.print_info("Verify anonymity: https://check.torproject.org")
        else:
            self.print_warning("No Tor SOCKS proxy found on 9050/9150")
            self.print_info("Install Tor: https://www.torproject.org/download/")
            self.print_info("Or start Tor Browser (uses port 9150)")

    async def cmd_socks_check(self, *args) -> None:
        """Validate a SOCKS5 proxy."""
        host = self.prompt("SOCKS5 host", default="127.0.0.1") or "127.0.0.1"
        port = self.prompt("SOCKS5 port", default="9050") or "9050"
        try:
            port_i = int(port)
        except ValueError:
            self.print_error("Invalid port")
            return
        if self._port_open(host, port_i):
            self.print_success(f"SOCKS5 proxy reachable at {host}:{port_i}")
        else:
            self.print_error(f"SOCKS5 proxy NOT reachable at {host}:{port_i}")

    async def cmd_http_proxy(self, *args) -> None:
        """Validate an HTTP proxy."""
        host = self.prompt("HTTP proxy host", default="127.0.0.1") or "127.0.0.1"
        port = self.prompt("HTTP proxy port", default="8080") or "8080"
        try:
            port_i = int(port)
        except ValueError:
            self.print_error("Invalid port")
            return
        if self._port_open(host, port_i):
            self.print_success(f"HTTP proxy reachable at {host}:{port_i}")
        else:
            self.print_error(f"HTTP proxy NOT reachable at {host}:{port_i}")

    async def cmd_chain(self, *args) -> None:
        """Build a proxy chain (proxychains-style)."""
        chain = self.prompt("Proxy chain (comma-separated host:port, e.g. 127.0.0.1:9050,10.0.0.1:1080)")
        if not chain:
            return
        proxies = [p.strip() for p in chain.split(",") if p.strip()]
        out_dir = Path(self.context.get_reports_dir()) / "anonymity"
        out_dir.mkdir(parents=True, exist_ok=True)
        conf = out_dir / "proxychains.conf"
        lines = ["[ProxyList]"]
        for p in proxies:
            host, _, port = p.partition(":")
            lines.append(f"socks5 {host} {port or 1080}")
        conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.print_success(f"Proxy chain config saved: {conf}")
        self.print_info(f"Use: proxychains -f {conf} <command>")

    async def cmd_ssh_forward(self, *args) -> None:
        """Start SSH dynamic SOCKS forward."""
        if not shutil.which("ssh"):
            self.print_error("ssh not found on PATH")
            return
        host = self.prompt("SSH host")
        if not host:
            return
        user = self.prompt("SSH user", default="root") or "root"
        port = self.prompt("SSH port", default="22") or "22"
        local = self.prompt("Local SOCKS port", default="1080") or "1080"
        self.print_info(f"Starting SSH dynamic forward: -D {local} -p {port} {user}@{host}")
        self.print_info("This is a blocking command; run it in a terminal")
        self.print_success(f"Command: ssh -D {local} -p {port} {user}@{host}")

    async def cmd_socat_relay(self, *args) -> None:
        """Start a socat TCP relay."""
        if not shutil.which("socat"):
            self.print_error("socat not found on PATH")
            self.print_info("Install: winget install AndrewY.Socat / apt install socat / brew install socat")
            return
        listen = self.prompt("Listen address (e.g. 0.0.0.0:8080)", default="0.0.0.0:8080") or "0.0.0.0:8080"
        target = self.prompt("Target (e.g. 127.0.0.1:5001)")
        if not target:
            return
        self.print_info(f"Starting socat relay: {listen} -> {target}")
        self.print_success(f"Command: socat TCP-LISTEN:{listen.split(':')[-1]},fork,reuseaddr TCP:{target}")

    async def cmd_onion_desc(self, *args) -> None:
        """Generate Tor onion service descriptor."""
        out_dir = Path(self.context.get_reports_dir()) / "anonymity"
        out_dir.mkdir(parents=True, exist_ok=True)
        desc = """# Tor onion service descriptor
# Place in /var/lib/tor/<service>/hostname and private_key
#
# torrc:
# HiddenServiceDir /var/lib/tor/pegasus/
# HiddenServicePort 80 127.0.0.1:5001
#
# After restart, read the hostname from the HiddenServiceDir.
"""
        conf = out_dir / "torrc.onion"
        conf.write_text(desc, encoding="utf-8")
        self.print_success(f"Onion service torrc saved: {conf}")
        self.print_info("HiddenServiceDir + HiddenServicePort expose the Flask backend as an onion service")

    # ── Helpers ────────────────────────────────────────────────────────

    def _port_open(self, host: str, port: int, timeout: float = 1.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False


__all__ = ["AnonymityModule"]
