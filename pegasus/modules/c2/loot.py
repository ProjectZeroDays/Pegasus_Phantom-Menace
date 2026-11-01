"""Seal loot at rest. Manifest carries the hashes."""
import base64
import hashlib
import json
import pathlib

from ..crypto import atrest


def seal_dir(root: pathlib.Path) -> dict:
    manifest = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix == ".enc":
            continue
        raw = path.read_bytes()
        manifest[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
        sealed = atrest.seal({"name": path.name,
                              "b64": base64.b64encode(raw).decode()})
        path.with_suffix(path.suffix + ".enc").write_bytes(sealed.encode())
        path.unlink()
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def open_file(path: pathlib.Path) -> bytes:
    payload = atrest.open_sealed(path.read_text())
    return base64.b64decode(payload["b64"])
