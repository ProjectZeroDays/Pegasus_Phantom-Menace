"""Signed self-update with rollback."""
import hashlib
import pathlib
import shutil
import zipfile

import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

STAGING = pathlib.Path.home() / ".pegasus" / "staging"


def _verify(blob: bytes, signature: bytes, pubkey_path: pathlib.Path) -> None:
    key = load_pem_public_key(pubkey_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise RuntimeError("pubkey is not Ed25519")
    key.verify(signature, blob)


def fetch(url: str, signature_url: str, pubkey_path: pathlib.Path) -> pathlib.Path:
    STAGING.mkdir(parents=True, exist_ok=True)
    blob = requests.get(url, timeout=120).content
    _verify(blob, requests.get(signature_url, timeout=30).content, pubkey_path)
    dest = STAGING / f"{hashlib.sha256(blob).hexdigest()[:12]}.zip"
    dest.write_bytes(blob)
    return dest


def apply(dest: pathlib.Path, target_root: pathlib.Path) -> dict:
    backup = STAGING / f"rollback-{dest.stem}"
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(target_root, backup)
    with zipfile.ZipFile(dest) as zf:
        zf.extractall(target_root)
    return {"applied": str(dest), "rollback": str(backup)}


def rollback(backup: pathlib.Path, target_root: pathlib.Path) -> None:
    shutil.rmtree(target_root)
    shutil.copytree(backup, target_root)
