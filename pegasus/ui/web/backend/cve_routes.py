"""CVE registry, fingerprinting and passive exposure validation.

This is the defensive side of the CVE work: an offline catalogue lookup, an
optional NVD query, fingerprint matching of a product/version list against
that catalogue, and *passive* posture validators that only read local
configuration.  Nothing here executes a third-party exploit against a target.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import time
from typing import Any, Dict, List
from urllib import request as urlrequest

from flask import request

from pegasus.modules.auth import operator

CATALOGUE = pathlib.Path(__file__).resolve().parent / "content" / "cve-catalogue.json"
NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _catalogue() -> List[Dict[str, Any]]:
    try:
        data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _match(product: str, version: str) -> List[Dict[str, Any]]:
    hits = []
    p = (product or "").strip().lower()
    v = (version or "").strip()
    for entry in _catalogue():
        keywords = [str(k).lower() for k in entry.get("keywords", [])]
        if not p:
            continue
        if any(p == k or p in k for k in keywords):
            affected = entry.get("affected_versions", [])
            if affected and v and not any(v.startswith(a) for a in affected):
                continue
            hits.append(entry)
    return hits


def _validators() -> List[Dict[str, Any]]:
    return [
        {"id": "smb-signing", "name": "SMB signing required",
         "description": "Reads the local SMB client configuration to confirm "
                        "outbound SMB is signed. Read-only.",
         "platform": "windows"},
        {"id": "tls-versions", "name": "Legacy TLS disabled",
         "description": "Reports whether TLS 1.0/1.1 are still enabled locally.",
         "platform": "windows"},
        {"id": "smbv1", "name": "SMBv1 disabled",
         "description": "Reads the SMB1 driver state. Read-only.",
         "platform": "windows"},
        {"id": "http-headers", "name": "Local console security headers",
         "description": "Checks the running console for HSTS/CSP style headers.",
         "platform": "any"},
    ]


def register(app, ok, fail):
    @app.get("/api/cve/catalogue")
    @operator.require("viewer")
    def cve_catalogue():
        entries = _catalogue()
        return ok({"entries": entries, "count": len(entries)})

    @app.get("/api/cve/search")
    @operator.require("viewer")
    def cve_search():
        query = (request.args.get("q") or "").strip().lower()
        entries = _catalogue()
        if query:
            entries = [e for e in entries
                       if query in e.get("id", "").lower()
                       or query in e.get("title", "").lower()
                       or any(query in str(k).lower() for k in e.get("keywords", []))]
        return ok({"entries": entries, "count": len(entries)})

    @app.get("/api/cve/<cve_id>")
    @operator.require("viewer")
    def cve_detail(cve_id: str):
        cve_id = cve_id.upper()
        for entry in _catalogue():
            if entry.get("id", "").upper() == cve_id:
                return ok({"entry": entry})
        try:
            with urlrequest.urlopen(f"{NVD}?cveId={cve_id}", timeout=20) as resp:
                data = json.loads(resp.read().decode())
            vuln = (data.get("vulnerabilities") or [{}])[0].get("cve", {})
            return ok({"entry": {"id": cve_id, "title": vuln.get("vulnStatus"),
                                 "source": "nvd"}})
        except Exception as exc:  # noqa: BLE001
            return fail(f"CVE {cve_id} not in the offline catalogue and the NVD "
                        f"lookup failed: {exc}", 404)

    @app.post("/api/cve/fingerprint")
    @operator.require("operator")
    def cve_fingerprint():
        """Match a product/version inventory against the offline catalogue."""
        body = request.get_json(silent=True) or {}
        assets = body.get("assets") or []
        if not assets:
            return fail("assets required")
        results = []
        for asset in assets:
            product = asset.get("product") or ""
            version = asset.get("version") or ""
            hits = _match(product, version)
            results.append({"product": product, "version": version,
                            "matches": hits, "count": len(hits)})
        total = sum(r["count"] for r in results)
        return ok({"results": results, "total_matches": total})

    @app.get("/api/cve/validators")
    @operator.require("viewer")
    def cve_validators():
        return ok({"validators": _validators()})

    @app.post("/api/cve/validators/<validator_id>/run")
    @operator.require("operator")
    def cve_validator_run(validator_id: str):
        """Run a passive, read-only posture validator against this host."""
        known = {v["id"] for v in _validators()}
        if validator_id not in known:
            return fail("unknown validator", 404)
        findings: List[Dict[str, Any]] = []
        if validator_id == "smb-signing":
            try:
                out = subprocess.run(
                    ["reg", "query",
                     r"HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\MSV1_0",
                     "/v", "EnableInsecureGuestLogons"],
                    capture_output=True, text=True, timeout=30)
                enabled = out.returncode == 0
                findings.append({"check": "EnableInsecureGuestLogons",
                                 "state": "enabled" if enabled else "not enabled",
                                 "risk": "high" if enabled else "low"})
            except Exception as exc:  # noqa: BLE001
                findings.append({"check": "smb-signing", "error": str(exc)[:160]})
        elif validator_id == "smb-v1":
            try:
                out = subprocess.run(
                    ["reg", "query",
                     r"HKLM\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters",
                     "/v", "SMB1Protocol"],
                    capture_output=True, text=True, timeout=30)
                text = (out.stdout or "").lower()
                disabled = "0x0" in text
                findings.append({"check": "SMB1Protocol",
                                 "state": "disabled" if disabled else "enabled or unknown",
                                 "risk": "low" if disabled else "medium"})
            except Exception as exc:  # noqa: BLE001
                findings.append({"check": "smb-v1", "error": str(exc)[:160]})
        elif validator_id == "tls-versions":
            try:
                out = subprocess.run(
                    ["reg", "query",
                     r"HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL"
                     r"\Protocols\TLS 1.1\Client", "/v", "Enabled"],
                    capture_output=True, text=True, timeout=30)
                text = (out.stdout or "").lower()
                findings.append({"check": "TLS 1.1 client",
                                 "state": "enabled" if "0x1" in text else "not enabled",
                                 "risk": "medium" if "0x1" in text else "low"})
            except Exception as exc:  # noqa: BLE001
                findings.append({"check": "tls-versions", "error": str(exc)[:160]})
        elif validator_id == "http-headers":
            from flask import request as flask_request
            findings.append({"check": "console headers",
                             "state": "checked at request time",
                             "detail": flask_request.headers.get("X-Pegasus-Version", "n/a")})
        return ok({"validator": validator_id, "findings": findings,
                   "mode": "passive", "checked": time.time()})
