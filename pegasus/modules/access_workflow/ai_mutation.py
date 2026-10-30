"""
Pegasus Phantom Menace v2 - AI Mutation Engine

Scans an APK (or a smali tree) for strings that antivirus engines and Play
Protect heuristics commonly key on, scores the exposure and emits a prioritised
mutation plan that keeps the payload functionally identical while changing the
signature surface.

The engine works offline: it never uploads the sample. Detection is string and
structure based, so it runs in seconds and is safe for air-gapped labs.

All analysis is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Strings that most commonly anchor AV signatures in Android payloads.
SIGNATURE_CORPUS: Dict[str, List[str]] = {
    "framework": [
        "metasploit",
        "meterpreter",
        "msfvenom",
        "com.metasploit.stage",
        "MainActivity",
        "Payload",
    ],
    "transport": [
        "reverse_tcp",
        "reverse_https",
        "LHOST",
        "LPORT",
        "stage",
        "stager",
    ],
    "crypto": [
        "AES/CBC/PKCS5Padding",
        "X509TrustManager",
        "checkServerTrusted",
        "TrustAllCerts",
    ],
    "reflection": [
        "java.lang.reflect",
        "Class.forName",
        "DexClassLoader",
        "dalvik.system",
    ],
    "persistence": [
        "BOOT_COMPLETED",
        "RECEIVE_BOOT_COMPLETED",
        "JobService",
        "AccessibilityService",
        "DeviceAdminReceiver",
    ],
}

# Mutation techniques, ordered from least to most invasive.
MUTATION_PLAYBOOK: List[Dict[str, str]] = [
    {
        "id": "string-split",
        "technique": "Split detected literal strings across smali const-string assignments and concatenate at runtime.",
        "effort": "low",
        "breaks_signature": "high",
        "applies_to": "framework,transport",
    },
    {
        "id": "string-xor",
        "technique": "XOR-encode literals with a per-build key and decode in a static initialiser.",
        "effort": "medium",
        "breaks_signature": "high",
        "applies_to": "framework,transport,crypto",
    },
    {
        "id": "asset-rename",
        "technique": "Rename asset and raw resource filenames and update the generated R references.",
        "effort": "low",
        "breaks_signature": "medium",
        "applies_to": "transport,persistence",
    },
    {
        "id": "package-suffix",
        "technique": "Append a random 6-character suffix to the application package and manifest component names.",
        "effort": "low",
        "breaks_signature": "medium",
        "applies_to": "framework",
    },
    {
        "id": "junk-classes",
        "technique": "Insert unused classes and dead branches so the DEX layout hash changes.",
        "effort": "medium",
        "breaks_signature": "low",
        "applies_to": "framework",
    },
    {
        "id": "trust-manager-swap",
        "technique": "Replace the stock TrustManager with an inline anonymous implementation.",
        "effort": "medium",
        "breaks_signature": "medium",
        "applies_to": "crypto,reflection",
    },
    {
        "id": "zip-reorder",
        "technique": "Rebuild the APK with reordered ZIP entries and zeroed timestamps, then re-sign.",
        "effort": "low",
        "breaks_signature": "medium",
        "applies_to": "framework,transport,persistence",
    },
    {
        "id": "reflection-loader",
        "technique": "Load the payload class through Class.forName so the direct reference disappears from the call graph.",
        "effort": "high",
        "breaks_signature": "high",
        "applies_to": "reflection",
    },
]

READABLE_EXTENSIONS = {".smali", ".xml", ".json", ".properties", ".txt"}


@dataclass
class SignatureHit:
    category: str
    literal: str
    locations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MutationPlan:
    sample: str
    sample_sha256: str
    size_bytes: int
    entries: int
    scanned_units: int
    hits: List[SignatureHit]
    exposure_score: int
    verdict: str
    recommendations: List[Dict[str, str]]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["hits"] = [hit.to_dict() if isinstance(hit, SignatureHit) else hit for hit in self.hits]
        return data


class MutationError(RuntimeError):
    """Raised when the sample cannot be read."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_units(path: Path) -> Iterable[tuple[str, bytes]]:
    """Yield (label, content) pairs for scanning."""
    if path.is_dir():
        for file in sorted(path.rglob("*")):
            if file.is_file() and file.suffix.lower() in READABLE_EXTENSIONS:
                yield str(file.relative_to(path)), file.read_bytes()
        return

    if not zipfile.is_zipfile(path):
        yield path.name, path.read_bytes()
        return

    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if name.endswith(".dex") or Path(name).suffix.lower() in READABLE_EXTENSIONS:
                try:
                    yield name, archive.read(info)
                except (KeyError, RuntimeError):
                    continue


def scan(sample: str | Path) -> Dict[str, Any]:
    """Scan a sample and return the raw hit map."""
    path = Path(sample).expanduser()
    if not path.exists():
        raise MutationError(f"Sample not found: {path}")

    hits: Dict[tuple[str, str], SignatureHit] = {}
    units = 0
    for label, blob in _iter_units(path):
        units += 1
        # Latin-1 keeps DEX string tables readable without decoding errors.
        text = blob.decode("latin-1", errors="ignore")
        lowered = text.lower()
        for category, literals in SIGNATURE_CORPUS.items():
            for literal in literals:
                if literal.lower() in lowered:
                    key = (category, literal)
                    hit = hits.setdefault(key, SignatureHit(category=category, literal=literal))
                    if len(hit.locations) < 5:
                        hit.locations.append(label)

    return {
        "sample": str(path),
        "units_scanned": units,
        "hits": [hit.to_dict() for hit in hits.values()],
    }


def _recommend(hit_categories: set[str]) -> List[Dict[str, str]]:
    recommendations = []
    for entry in MUTATION_PLAYBOOK:
        applies = set(entry["applies_to"].split(","))
        if applies & hit_categories or "framework" in hit_categories:
            recommendations.append(dict(entry))
    # Always finish with packaging hygiene even with no literal hits.
    if not recommendations:
        recommendations = [dict(item) for item in MUTATION_PLAYBOOK if item["effort"] == "low"]
    return recommendations


def analyse(sample: str | Path, output: Optional[str | Path] = None) -> Dict[str, Any]:
    """Scan a sample, score exposure and return a mutation plan."""
    path = Path(sample).expanduser()
    if not path.exists():
        raise MutationError(f"Sample not found: {path}")

    raw = scan(path)
    hits = raw["hits"]
    categories = {hit["category"] for hit in hits}

    score = min(100, len(hits) * 9 + len(categories) * 6)
    if score >= 70:
        verdict = "likely detected"
    elif score >= 40:
        verdict = "borderline"
    elif score > 0:
        verdict = "low signal"
    else:
        verdict = "clean of known literals"

    size = path.stat().st_size if path.is_file() else 0
    entries = raw["units_scanned"]

    plan = MutationPlan(
        sample=str(path),
        sample_sha256=_sha256(path) if path.is_file() else "",
        size_bytes=size,
        entries=entries,
        scanned_units=raw["units_scanned"],
        hits=[SignatureHit(**hit) for hit in hits],
        exposure_score=score,
        verdict=verdict,
        recommendations=_recommend(categories),
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    ).to_dict()

    if output:
        out = Path(output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        plan["report"] = str(out)
    return plan


def apply_string_xor(sample: str | Path, key: int = 0x5A, output: Optional[str | Path] = None) -> Dict[str, Any]:
    """
    Write an XOR-obfuscated copy of every readable unit.

    This does not patch DEX bytecode for you; it produces the string blob that
    a smali patch or build step consumes, plus the decoded map for reference.
    """
    path = Path(sample).expanduser()
    if not path.exists():
        raise MutationError(f"Sample not found: {path}")
    out = Path(output).expanduser() if output else path.with_suffix(path.suffix + ".xor")
    out.mkdir(parents=True, exist_ok=True)

    manifest = []
    for label, blob in _iter_units(path):
        encoded = bytes(byte ^ key for byte in blob)
        target = out / re.sub(r"[\\/:*?\"<>|]", "_", label)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
        manifest.append({"unit": label, "output": str(target), "size": len(blob)})

    (out / "mutation_manifest.json").write_text(
        json.dumps({"key": hex(key), "units": manifest}, indent=2), encoding="utf-8"
    )
    return {"output": str(out), "key": hex(key), "units": len(manifest)}


__all__ = ["MutationError", "scan", "analyse", "apply_string_xor", "MUTATION_PLAYBOOK"]
