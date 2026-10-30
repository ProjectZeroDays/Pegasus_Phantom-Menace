"""
Pegasus Phantom Menace v2 - Zero-Click Exploits Package

Zero-click and zero-day exploits for Android devices, IoT/TVs, NFC, Bluetooth,
SMS, Messenger, WhatsApp, Telegram, Discord, Slack, Signal, Email, MITM spoofed
and self-signed Root CA attacks.

Every vector is indexed in :mod:`pegasus.modules.access_workflow.zero_click.registry`
so the CLI, dashboard and workflow engine can enumerate and dispatch them
without hard-coding module paths.

All exploits are for authorized security research and penetration testing only.
"""

from .registry import (
    EXPLOITS,
    ZeroClickError,
    ZeroClickExploit,
    device_families,
    get_exploit,
    list_exploits,
    run_all,
    run_exploit,
)

__all__ = [
    "EXPLOITS",
    "ZeroClickError",
    "ZeroClickExploit",
    "device_families",
    "get_exploit",
    "list_exploits",
    "run_all",
    "run_exploit",
]
