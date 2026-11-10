"""Cryptomator-style encrypted vault for operator loot.

Items are encrypted client-side of the operator session and stored under
``~/.pegasus/vault``.  AES-256-GCM is used when the optional ``cryptography``
package is present; otherwise a documented HMAC-SHA256 keystream cipher with a
per-item MAC is used so the store is never left unprotected.

The vault is a *store*: it holds sealed artefacts (evidence bundles, exported
reports, capture artifacts).  It never cracks anything and never holds wallet
seed material.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import secrets
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.auth import operator

VAULT_DIR = pathlib.Path.home() / ".pegasus" / "vault"
INDEX_FILE = pathlib.Path.home() / ".pegasus" / "vault_index.json"
MASTER_FILE = pathlib.Path.home() / ".pegasus" / "vault_master.key"
MAX_ITEM_BYTES = 8 * 1024 * 1024


def _aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM
    except Exception:
        return None


def _read_index() -> Dict[str, Any]:
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}


def _write_index(data: Dict[str, Any]) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _master_key() -> bytes:
    if not MASTER_FILE.exists():
        MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        MASTER_FILE.write_bytes(secrets.token_bytes(32))
        try:
            os.chmod(MASTER_FILE, 0o600)
        except Exception:
            pass
    return MASTER_FILE.read_bytes()


def _encrypt(plain: bytes) -> Dict[str, Any]:
    key = _master_key()
    nonce = secrets.token_bytes(12)
    aesgcm = _aesgcm()
    if aesgcm is not None:
        blob = aesgcm(key).encrypt(nonce, plain, None)
        return {"alg": "AES-256-GCM", "nonce": nonce.hex(), "blob": blob.hex()}
    stream = _keystream(key, nonce, len(plain))
    cipher = bytes(a ^ b for a, b in zip(plain, stream))
    tag = hmac.new(key, nonce + cipher, hashlib.sha256).hexdigest()
    return {"alg": "HMAC-SHA256-CTR", "nonce": nonce.hex(), "blob": cipher.hex(),
            "tag": tag}


def _decrypt(record: Dict[str, Any]) -> bytes:
    key = _master_key()
    nonce = bytes.fromhex(record["nonce"])
    blob = bytes.fromhex(record["blob"])
    if record.get("alg") == "AES-256-GCM":
        aesgcm = _aesgcm()
        if aesgcm is None:
            raise RuntimeError("cryptography package required to open this item")
        return aesgcm(key).decrypt(nonce, blob, None)
    stream = _keystream(key, nonce, len(blob))
    plain = bytes(a ^ b for a, b in zip(blob, stream))
    tag = hmac.new(key, nonce + blob, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(tag, record.get("tag", "")):
        raise RuntimeError("vault item failed integrity check")
    return plain


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += hmac.new(key, nonce + counter.to_bytes(4, "big"),
                        hashlib.sha256).digest()
        counter += 1
    return out[:length]


def register(app, ok, fail):
    @app.get("/api/vault/status")
    @operator.require("viewer")
    def vault_status():
        index = _read_index()
        return ok({
            "items": len(index.get("items", [])),
            "cipher": "AES-256-GCM" if _aesgcm() else "HMAC-SHA256-CTR",
            "master_key_present": MASTER_FILE.exists(),
            "directory": str(VAULT_DIR),
        })

    @app.get("/api/vault/items")
    @operator.require("viewer")
    def vault_list():
        op = operator.current()
        index = _read_index()
        items = [i for i in index.get("items", []) if i.get("owner") == op["user"]]
        return ok({"items": items})

    @app.post("/api/vault/items")
    @operator.require("operator")
    def vault_store():
        """Seal an artefact into the vault."""
        op = operator.current()
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return fail("name required")
        content = body.get("content")
        if content is None:
            return fail("content required")
        if isinstance(content, str):
            plain = content.encode("utf-8")
        else:
            plain = bytes(content)
        if len(plain) > MAX_ITEM_BYTES:
            return fail("item exceeds 8 MB")
        record = _encrypt(plain)
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        item_id = secrets.token_hex(8)
        target = VAULT_DIR / f"{item_id}.seal"
        target.write_text(json.dumps(record), encoding="utf-8")
        index = _read_index()
        entry = {"id": item_id, "name": name, "owner": op["user"],
                 "kind": body.get("kind") or "artifact",
                 "tags": body.get("tags") or [],
                 "bytes": len(plain), "cipher": record["alg"],
                 "created": time.time()}
        index.setdefault("items", []).append(entry)
        _write_index(index)
        return ok({"item": entry})

    @app.get("/api/vault/items/<item_id>")
    @operator.require("viewer")
    def vault_open(item_id: str):
        op = operator.current()
        index = _read_index()
        entry = next((i for i in index.get("items", []) if i.get("id") == item_id), None)
        if not entry:
            return fail("item not found", 404)
        if entry.get("owner") != op["user"] and operator.current().get("role") != "admin":
            return fail("not your item", 403)
        target = VAULT_DIR / f"{item_id}.seal"
        if not target.is_file():
            return fail("sealed blob missing", 404)
        try:
            plain = _decrypt(json.loads(target.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            return fail(f"cannot open item: {exc}", 500)
        try:
            text = plain.decode("utf-8")
        except UnicodeDecodeError:
            text = plain.hex()
        return ok({"item": entry, "content": text})

    @app.delete("/api/vault/items/<item_id>")
    @operator.require("operator")
    def vault_delete(item_id: str):
        op = operator.current()
        index = _read_index()
        items = index.get("items", [])
        entry = next((i for i in items if i.get("id") == item_id), None)
        if not entry:
            return fail("item not found", 404)
        if entry.get("owner") != op["user"] and operator.current().get("role") != "admin":
            return fail("not your item", 403)
        items[:] = [i for i in items if i.get("id") != item_id]
        _write_index(index)
        target = VAULT_DIR / f"{item_id}.seal"
        if target.is_file():
            target.unlink()
        return ok({"deleted": True})
