"""
Pegasus Phantom Menace v2 - Zero-Click Exploit Registry

A single, importable index of every zero-click exploit shipped with the
platform. The registry is consumed by the Command Factory, the dashboard API
and the workflow engine, so no caller has to know which module or function
implements a given device family.

All exploits are for authorized security research and penetration testing only.
"""

from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# Modules are imported lazily by ``_load`` so the registry itself stays cheap
# and can be imported from a web worker without pulling in subprocess helpers.
MODULE_PREFIX = "pegasus.modules.access_workflow.zero_click."


@dataclass(frozen=True)
class ZeroClickExploit:
    """Metadata for a single zero-click exploit vector."""

    key: str
    module: str
    function: str
    device_family: str
    transport: str
    cve: str
    description: str
    affects: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


EXPLOITS: Dict[str, ZeroClickExploit] = {
    exploit.key: exploit
    for exploit in [
        ZeroClickExploit(
            key="android_binder",
            module=MODULE_PREFIX + "android_general_zero_click",
            function="exploit_android_binder",
            device_family="android",
            transport="binder",
            cve="CVE-2019-2215 / CVE-2020-0041",
            description="Binder IPC use-after-free and out-of-bounds write chain for kernel code execution.",
            affects=["Android 8.0 - 11"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="android_mediacodec",
            module=MODULE_PREFIX + "android_general_zero_click",
            function="exploit_android_mediacodec",
            device_family="android",
            transport="media",
            cve="CVE-2024-43093 (media framework)",
            description="MediaCodec/MP4 parser corruption delivered through a dropped media file.",
            affects=["Android 10 - 14"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="android_bluetooth",
            module=MODULE_PREFIX + "android_general_zero_click",
            function="exploit_android_bluetooth",
            device_family="android",
            transport="bluetooth",
            cve="CVE-2023-45866",
            description="Bluetooth HFP/HID keystroke injection requiring no device confirmation.",
            affects=["Android 9 - 14"],
            requires=["bluetooth"],
        ),
        ZeroClickExploit(
            key="oneplus_oxygenos",
            module=MODULE_PREFIX + "oneplus_zero_click",
            function="exploit_oneplus_oxygenos",
            device_family="oneplus",
            transport="oem-service",
            cve="OxygenOS service surface",
            description="OxygenOS system-service intent surface enumeration and abuse chain.",
            affects=["OnePlus OxygenOS 12 - 14"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="oneplus_qualcomm_modem",
            module=MODULE_PREFIX + "oneplus_zero_click",
            function="exploit_oneplus_qualcomm_modem",
            device_family="oneplus",
            transport="baseband",
            cve="Qualcomm modem malformed frame",
            description="Qualcomm baseband frame handling probe for remote modem crashes.",
            affects=["OnePlus Snapdragon devices"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="pixel8_modem",
            module=MODULE_PREFIX + "pixel8_zero_click",
            function="exploit_pixel8_modem",
            device_family="pixel8",
            transport="baseband",
            cve="Tensor G3 modem",
            description="Malformed SIB frame probe against the Tensor G3 baseband.",
            affects=["Google Pixel 8 / 8 Pro"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="pixel8_wifi",
            module=MODULE_PREFIX + "pixel8_zero_click",
            function="exploit_pixel8_wifi",
            device_family="pixel8",
            transport="wifi",
            cve="Broadcom WiFi frame",
            description="WiFi management-frame probe against the Pixel 8 Broadcom stack.",
            affects=["Google Pixel 8 / 8 Pro"],
            requires=["wifi"],
        ),
        ZeroClickExploit(
            key="pixel8_titan_m2_usb",
            module=MODULE_PREFIX + "pixel8_zero_click",
            function="exploit_pixel8_titan_m2_usb",
            device_family="pixel8",
            transport="usb",
            cve="Titan M2 accessory path",
            description="USB accessory descriptor probe against the Titan M2 secure element path.",
            affects=["Google Pixel 8 / 8 Pro"],
            requires=["usb"],
        ),
        ZeroClickExploit(
            key="pixel8_nfc",
            module=MODULE_PREFIX + "pixel8_zero_click",
            function="exploit_pixel8_nfc_zero_click",
            device_family="pixel8",
            transport="nfc",
            cve="NFC NDEF parser",
            description="NDEF tag payload crafted to trigger NFC parser handling without confirmation.",
            affects=["Google Pixel 8 / 8 Pro"],
            requires=["nfc"],
        ),
        ZeroClickExploit(
            key="samsung_exynos_modem",
            module=MODULE_PREFIX + "samsung_s24_zero_click",
            function="exploit_s24_exynos_modem",
            device_family="samsung",
            transport="baseband",
            cve="Exynos 2400 modem",
            description="Malformed cellular frame probe against the Exynos 2400 baseband.",
            affects=["Samsung Galaxy S24 (Exynos)"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="samsung_knox_bypass",
            module=MODULE_PREFIX + "samsung_s24_zero_click",
            function="exploit_s24_knox_bypass",
            device_family="samsung",
            transport="knox",
            cve="Knox service surface",
            description="Knox platform service enumeration and policy bypass chain.",
            affects=["Samsung Galaxy S24 / S24 Ultra"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="xiaomi_miui_service",
            module=MODULE_PREFIX + "xiaomi_zero_click",
            function="exploit_xiaomi_miui_service",
            device_family="xiaomi",
            transport="oem-service",
            cve="MIUI service surface",
            description="MIUI system-service intent surface abuse chain.",
            affects=["Xiaomi MIUI 13 - 14"],
            requires=["adb"],
        ),
        ZeroClickExploit(
            key="xiaomi_hyperos",
            module=MODULE_PREFIX + "xiaomi_zero_click",
            function="exploit_xiaomi_hyperos",
            device_family="xiaomi",
            transport="oem-service",
            cve="HyperOS service surface",
            description="HyperOS service surface probe and privilege boundary checks.",
            affects=["Xiaomi HyperOS 1.x"],
            requires=["adb"],
        ),
    ]
}


class ZeroClickError(RuntimeError):
    """Raised when an exploit key is unknown or fails to load."""


def _load(exploit: ZeroClickExploit):
    module = importlib.import_module(exploit.module)
    try:
        return getattr(module, exploit.function)
    except AttributeError as exc:  # pragma: no cover - defensive
        raise ZeroClickError(f"{exploit.module}.{exploit.function} is missing") from exc


def list_exploits(
    device_family: Optional[str] = None,
    transport: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return exploit metadata, optionally filtered by device family/transport."""
    results = []
    for exploit in EXPLOITS.values():
        if device_family and exploit.device_family != device_family:
            continue
        if transport and exploit.transport != transport:
            continue
        results.append(exploit.to_dict())
    return results


def get_exploit(key: str) -> Dict[str, Any]:
    """Return metadata for one exploit key."""
    if key not in EXPLOITS:
        raise ZeroClickError(f"Unknown zero-click exploit: {key}")
    return EXPLOITS[key].to_dict()


def run_exploit(key: str, **kwargs: Any) -> Dict[str, Any]:
    """Run one exploit by key and return its result dictionary."""
    if key not in EXPLOITS:
        raise ZeroClickError(f"Unknown zero-click exploit: {key}")
    exploit = EXPLOITS[key]
    fn = _load(exploit)
    result = fn(**kwargs)
    enriched = dict(result if isinstance(result, dict) else {"result": result})
    enriched.setdefault("exploit", exploit.key)
    enriched.setdefault("device_family", exploit.device_family)
    enriched.setdefault("transport", exploit.transport)
    return enriched


def run_all(device_family: Optional[str] = None, **kwargs: Any) -> List[Dict[str, Any]]:
    """Run every (optionally filtered) exploit, collecting failures inline."""
    results = []
    for key, exploit in EXPLOITS.items():
        if device_family and exploit.device_family != device_family:
            continue
        try:
            results.append(run_exploit(key, **kwargs))
        except Exception as exc:  # keep the sweep going
            results.append({"exploit": key, "status": "error", "error": str(exc)})
    return results


def device_families() -> List[str]:
    """Return the sorted device families covered by the registry."""
    return sorted({exploit.device_family for exploit in EXPLOITS.values()})


__all__ = [
    "EXPLOITS",
    "ZeroClickExploit",
    "ZeroClickError",
    "list_exploits",
    "get_exploit",
    "run_exploit",
    "run_all",
    "device_families",
]
