"""
Pegasus Phantom Menace v2 - FRP Unlock Workflow (access_workflow package)

Thin, registry-friendly facade over the adaptive Factory Reset Protection
workflow. The heavy lifting lives in :mod:`pegasus.modules.frp_unlock`; this
module re-exports it with stable metadata, a structured result envelope and an
entry point the CLI, dashboard and workflow engine can call without knowing the
implementation layout.

The workflow tries five methods in order, skipping variants that cannot apply
to the detected device:

1. TalkBack accessibility detour
2. Emergency-call intent detour
3. ADB-over-wireless enrolment
4. Download mode / Odin (Samsung only)
5. FRP bypass APK install

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pegasus.modules.frp_unlock import FRPCUnlockWorkflow, run_frp_unlock as _run_frp_unlock

KEY = "frp_unlock"
NAME = "Factory Reset Protection unlock"
DESCRIPTION = (
    "Adaptive five-method FRP bypass chain: TalkBack detour, emergency call, "
    "wireless ADB, download mode (Samsung) and bypass APK install."
)
METHODS: List[Dict[str, str]] = [
    {"key": "talkback_accessibility", "label": "TalkBack accessibility detour", "requires": "any"},
    {"key": "emergency_call", "label": "Emergency call intent detour", "requires": "any"},
    {"key": "adb_wireless", "label": "Wireless ADB enrolment", "requires": "adb"},
    {"key": "download_mode", "label": "Download mode / Odin", "requires": "samsung"},
    {"key": "bypass_apk", "label": "FRP bypass APK install", "requires": "bypass apk"},
]


def metadata() -> Dict[str, Any]:
    """Describe the workflow for registries and the dashboard."""
    return {
        "key": KEY,
        "name": NAME,
        "description": DESCRIPTION,
        "methods": METHODS,
        "requires_device": True,
    }


def run(serial: Optional[str] = None, bypass_apk: Optional[str] = None) -> Dict[str, Any]:
    """Execute the adaptive chain and return a structured result."""
    result = _run_frp_unlock(serial=serial, bypass_apk=bypass_apk)
    enriched = dict(result or {})
    enriched.setdefault("workflow", KEY)
    enriched.setdefault("method_count", len(METHODS))
    return enriched


def plan(android_api: int = 33, is_samsung: bool = False, has_adb: bool = False) -> List[Dict[str, str]]:
    """Return the method order a device would follow, annotated with skips."""
    ordered = []
    for method in METHODS:
        entry = dict(method)
        if method["key"] == "talkback_accessibility" and android_api >= 33:
            entry["note"] = "restricted on Android 13+; attempted first but expected to be skipped"
        if method["key"] == "download_mode" and not is_samsung:
            entry["note"] = "skipped: not a Samsung device"
        if method["key"] == "adb_wireless" and not has_adb:
            entry["note"] = "needs ADB-over-wireless reachability"
        ordered.append(entry)
    return ordered


__all__ = ["FRPCUnlockWorkflow", "KEY", "NAME", "DESCRIPTION", "METHODS", "metadata", "run", "plan"]
