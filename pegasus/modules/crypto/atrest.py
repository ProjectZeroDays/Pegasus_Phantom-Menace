"""AES-GCM at rest, Argon2id-derived key."""
import base64
import json
import os
import pathlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

KEYFILE = pathlib.Path.home() / ".pegasus" / "atrest.key"
SALT_LEN, NONCE_LEN = 16, 12


def _derive(passphrase: str, salt: bytes) -> bytes:
    return Argon2id(salt=salt, length=32, iterations=3, lanes=4,
                    memory_cost=65536).derive(passphrase.encode())


def init(passphrase: str) -> None:
    salt = os.urandom(SALT_LEN)
    KEYFILE.parent.mkdir(parents=True, exist_ok=True)
    KEYFILE.write_bytes(salt + _derive(passphrase, salt))
    os.chmod(KEYFILE, 0o600)


def ensure(passphrase: str | None = None) -> None:
    if KEYFILE.exists():
        return
    if not passphrase:
        raise RuntimeError("passphrase required for first init")
    init(passphrase)


def _key() -> bytes:
    if not KEYFILE.exists():
        raise RuntimeError("atrest not initialised")
    return KEYFILE.read_bytes()[SALT_LEN:]


def seal(data: dict) -> str:
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(_key()).encrypt(nonce, json.dumps(data).encode(), None)
    return base64.b64encode(nonce + ct).decode()


def open_sealed(token: str) -> dict:
    raw = base64.b64decode(token)
    return json.loads(AESGCM(_key()).decrypt(raw[:NONCE_LEN], raw[NONCE_LEN:], None))
