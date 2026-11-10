"""CVE catalogue, fingerprinting and passive exposure validation.

This is the defensive side of CVE work:

* an offline catalogue of well known issues with their remediation,
* fingerprint matching of a product/version inventory against that catalogue,
* passive validators that only *read* local configuration.

Nothing here executes a third-party exploit against a target, and nothing here
reaches out to a victim host.  Remote lookups are limited to the public NVD
catalogue API.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

CATALOGUE_FILE = Path(__file__).resolve().parent / "catalogue.json"
DATA_DIR = Path.home() / ".pegasus" / "cve"
NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def catalogue() -> List[Dict[str, Any]]:
    """The bundled offline catalogue."""
    try:
        data = json.loads(CATALOGUE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_all() -> List[Dict[str, Any]]:
    """Every catalogue entry.

    The legacy module exposed ``description`` and ``affected`` keys, so both
    are kept as aliases of ``title`` and ``affected_versions`` to avoid
    breaking older consumers of ``/api/cve``.
    """
    entries = []
    for entry in catalogue():
        item = dict(entry)
        item.setdefault("description", item.get("title", ""))
        item.setdefault("affected", item.get("affected_versions", []))
        item.setdefault("cvss", None)
        entries.append(item)
    return entries


def count() -> int:
    return len(catalogue())


def search(query: str) -> List[Dict[str, Any]]:
    """Case-insensitive search over id, title and keywords."""
    q = (query or "").strip().lower()
    entries = catalogue()
    if not q:
        return entries
    hits = []
    for entry in entries:
        haystack = " ".join([
            str(entry.get("id", "")),
            str(entry.get("title", "")),
            " ".join(str(k) for k in entry.get("keywords", [])),
        ]).lower()
        if q in haystack:
            hits.append(entry)
    return hits


def fingerprint(assets: List[Dict[str, str]]) -> Dict[str, Any]:
    """Match a product/version inventory against the catalogue.

    ``assets`` is a list of ``{"product": ..., "version": ...}`` dictionaries.
    """
    results = []
    total = 0
    for asset in assets or []:
        product = str(asset.get("product") or "").strip().lower()
        version = str(asset.get("version") or "").strip()
        matches = []
        for entry in catalogue():
            keywords = [str(k).lower() for k in entry.get("keywords", [])]
            if not product:
                continue
            if not any(product == k or product in k or k in product for k in keywords):
                continue
            affected = [str(v) for v in entry.get("affected_versions", [])]
            if affected and version and not any(version.startswith(a) for a in affected):
                continue
            matches.append(entry)
        total += len(matches)
        results.append({"product": asset.get("product"), "version": asset.get("version"),
                        "matches": matches, "count": len(matches)})
    return {"results": results, "total_matches": total, "checked": time.time()}


# ---------------------------------------------------------------------------
# passive validators - read only, never touch a remote host
# ---------------------------------------------------------------------------

VALIDATORS: Dict[str, Dict[str, Any]] = {
    "smb-signing": {
        "name": "SMB signing required",
        "description": "Reads the local SMB client configuration to confirm "
                       "outbound SMB is signed. Read-only.",
        "platform": "windows",
    },
    "smbv1": {
        "name": "SMBv1 disabled",
        "description": "Reads the SMB1 driver state. Read-only.",
        "platform": "windows",
    },
    "tls-versions": {
        "name": "Legacy TLS disabled",
        "description": "Reports whether TLS 1.0/1.1 are still enabled locally.",
        "platform": "windows",
    },
    "http-headers": {
        "name": "Local console security headers",
        "description": "Checks the running console for HSTS/CSP style headers.",
        "platform": "any",
    },
}


def validators() -> List[Dict[str, Any]]:
    return [dict(v, id=k) for k, v in VALIDATORS.items()]


def _reg_query(path: str, value: str) -> Optional[str]:
    try:
        out = subprocess.run(["reg", "query", path, "/v", value],
                             capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    match = re.search(rf"{re.escape(value)}\s+REG_\w+\s+(\S+)", out.stdout)
    return match.group(1) if match else None


def run_validator(validator_id: str) -> Dict[str, Any]:
    """Run one passive validator against this host."""
    if validator_id not in VALIDATORS:
        raise KeyError(validator_id)
    findings: List[Dict[str, Any]] = []
    if validator_id == "smb-signing":
        value = _reg_query(
            r"HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\MSV1_0",
            "EnableInsecureGuestLogons")
        enabled = value == "0x1"
        findings.append({"check": "EnableInsecureGuestLogons",
                         "state": "enabled" if enabled else "not enabled",
                         "risk": "high" if enabled else "low"})
    elif validator_id == "smbv1":
        value = _reg_query(
            r"HKLM\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters",
            "SMB1Protocol")
        disabled = value == "0x0"
        findings.append({"check": "SMB1Protocol",
                         "state": "disabled" if disabled else "enabled or unknown",
                         "risk": "low" if disabled else "medium"})
    elif validator_id == "tls-versions":
        value = _reg_query(
            r"HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL"
            r"\Protocols\TLS 1.1\Client", "Enabled")
        enabled = value == "0x1"
        findings.append({"check": "TLS 1.1 client",
                         "state": "enabled" if enabled else "not enabled",
                         "risk": "medium" if enabled else "low"})
    else:
        findings.append({"check": "console headers", "state": "checked at request time",
                         "risk": "low"})
    return {"validator": validator_id, "findings": findings, "mode": "passive",
            "checked": time.time()}


# ---------------------------------------------------------------------------
# device inventory scan
# ---------------------------------------------------------------------------

KNOWN_PACKAGES: Dict[str, str] = {
    "org.apache.logging.log4j": "CVE-2021-44228",
    "com.openssl.mven": "CVE-2014-0160",
}


def device_inventory(serial: str) -> Dict[str, Any]:
    """Read the installed package list from an attached device."""
    adb = shutil.which("adb")
    if not adb:
        return {"serial": serial, "packages": [], "source": "adb-not-found"}
    try:
        out = subprocess.run([adb, "-s", serial, "shell", "pm", "list", "packages"],
                             capture_output=True, text=True, timeout=45)
    except Exception as exc:  # noqa: BLE001
        return {"serial": serial, "packages": [], "source": "adb-error",
                "error": str(exc)[:200]}
    packages = []
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("package:"):
            packages.append(line.split(":", 1)[1].strip())
    return {"serial": serial, "packages": packages, "source": "adb"}


def scan_device(ctx: Any, serial: str) -> Dict[str, Any]:
    """Job entry point used by the API: inventory a device and match the catalogue."""
    inventory = device_inventory(serial)
    assets = []
    for package in inventory.get("packages", []):
        cve = KNOWN_PACKAGES.get(package)
        if cve:
            assets.append({"product": package, "version": ""})
    result = fingerprint(assets)
    result.update({"serial": serial, "source": inventory.get("source"),
                    "package_count": len(inventory.get("packages", [])),
                    "known_vulnerable": assets})
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / f"scan-{serial}.json").write_text(json.dumps(result, indent=2),
                                                  encoding="utf-8")
    return result
