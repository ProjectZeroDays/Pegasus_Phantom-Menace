"""
Pegasus Phantom Menace v2 - Payload DNA Tagging

Every payload build can be stamped with a DNA tag: a stable, collision-checked
identifier derived from the payload bytes, target, campaign and build time.

The registry lives beside the samples, so a payload recovered from a device can
be matched back to the campaign, operator and build that produced it even after
the file is renamed or the campaign is archived.

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_VERSION = 1
TAG_LENGTH = 16


class DNAError(RuntimeError):
    """Raised for invalid registry state."""


def _registry_path(registry_dir: str | Path) -> Path:
    return Path(registry_dir).expanduser() / "dna_registry.json"


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": REGISTRY_VERSION, "tags": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DNAError(f"Corrupt DNA registry: {path}") from exc
    data.setdefault("version", REGISTRY_VERSION)
    data.setdefault("tags", {})
    return data


def _save(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def payload_digest(payload_path: str | Path) -> str:
    """SHA-256 of the payload bytes (empty string when the file is absent)."""
    path = Path(payload_path).expanduser()
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_tag(
    payload_path: str | Path,
    target: str,
    campaign: str = "default",
    registry_dir: str | Path = "~/.pegasus/dna",
    notes: str = "",
) -> Dict[str, Any]:
    """Create and persist a DNA tag for a payload build."""
    payload = Path(payload_path).expanduser()
    digest = payload_digest(payload)
    seed = f"{digest}|{payload.name}|{target}|{campaign}|{time.time_ns()}"
    tag = hashlib.sha256(seed.encode()).hexdigest()[:TAG_LENGTH]

    registry = _registry_path(registry_dir)
    data = _load(registry)
    while tag in data["tags"]:  # practically impossible, but cheap
        tag = hashlib.sha256((seed + tag).encode()).hexdigest()[:TAG_LENGTH]

    record = {
        "tag": tag,
        "payload": str(payload),
        "payload_name": payload.name,
        "payload_sha256": digest,
        "payload_size": payload.stat().st_size if payload.exists() else 0,
        "target": target,
        "campaign": campaign,
        "notes": notes,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    data["tags"][tag] = record
    _save(registry, data)
    return record


def generate_batch(
    payload_paths: List[str | Path],
    target: str,
    campaign: str = "default",
    registry_dir: str | Path = "~/.pegasus/dna",
) -> List[Dict[str, Any]]:
    """Tag a whole batch of payloads under one campaign."""
    return [
        generate_tag(path, target, campaign=campaign, registry_dir=registry_dir)
        for path in payload_paths
    ]


def lookup(tag: str, registry_dir: str | Path = "~/.pegasus/dna") -> Optional[Dict[str, Any]]:
    """Resolve a tag to its record."""
    return _load(_registry_path(registry_dir))["tags"].get(tag)


def match_payload(payload_path: str | Path, registry_dir: str | Path = "~/.pegasus/dna") -> List[Dict[str, Any]]:
    """Find every tag whose recorded SHA-256 matches the given file."""
    digest = payload_digest(payload_path)
    if not digest:
        return []
    data = _load(_registry_path(registry_dir))
    return [record for record in data["tags"].values() if record.get("payload_sha256") == digest]


def list_tags(
    campaign: Optional[str] = None,
    registry_dir: str | Path = "~/.pegasus/dna",
) -> List[Dict[str, Any]]:
    """List tags, newest first, optionally filtered by campaign."""
    records = list(_load(_registry_path(registry_dir))["tags"].values())
    if campaign:
        records = [record for record in records if record.get("campaign") == campaign]
    return sorted(records, key=lambda record: record.get("created_at", ""), reverse=True)


def export_csv(registry_dir: str | Path = "~/.pegasus/dna") -> str:
    """Export the registry as CSV text."""
    columns = ["tag", "campaign", "target", "payload_name", "payload_sha256", "created_at", "notes"]
    lines = [",".join(columns)]
    for record in list_tags(registry_dir=registry_dir):
        lines.append(",".join(str(record.get(column, "")).replace(",", ";") for column in columns))
    return "\n".join(lines)


__all__ = [
    "DNAError",
    "generate_tag",
    "generate_batch",
    "lookup",
    "match_payload",
    "list_tags",
    "export_csv",
    "payload_digest",
]
