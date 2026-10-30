"""
Pegasus Phantom Menace v2 - Steganography Delivery

Hides a delivery URL (or any short blob) in the least-significant bits of a
cover image and recovers it later. The frame is self-describing and
checksummed, so a truncated or re-encoded image fails loudly instead of
producing garbage.

Frame layout::

    b"PGST" | version(1) | sha256(payload)[:4] | length(4, big endian) | payload

Bits are written into RGB channels only (alpha is untouched so PNG transparency
survives). Encryption is optional XOR with a caller-supplied key.

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Optional

MAGIC = b"PGST"
VERSION = 1
HEADER = len(MAGIC) + 1 + 4 + 4


class StegoError(RuntimeError):
    """Raised when the carrier is too small or the frame is invalid."""


def _bits(data: bytes):
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def _xor(data: bytes, key: Optional[str]) -> bytes:
    if not key:
        return data
    stream = hashlib.sha256(key.encode()).digest()
    return bytes(byte ^ stream[index % len(stream)] for index, byte in enumerate(data))


def capacity_bytes(width: int, height: int) -> int:
    """Usable payload bytes for an RGB image of these dimensions."""
    return max(0, (width * height * 3) // 8 - HEADER)


def embed(
    cover: str | Path,
    payload: str | bytes,
    output: str | Path,
    key: Optional[str] = None,
) -> dict:
    """Embed ``payload`` into ``cover`` and write ``output``."""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise StegoError("Pillow is required: pip install pillow") from exc

    cover_path = Path(cover).expanduser()
    if not cover_path.exists():
        raise StegoError(f"Cover image not found: {cover_path}")

    raw = payload.encode() if isinstance(payload, str) else payload
    if not raw:
        raise StegoError("Payload is empty")
    body = _xor(raw, key)
    frame = MAGIC + bytes([VERSION]) + hashlib.sha256(body).digest()[:4] + struct.pack(">I", len(body)) + body

    image = Image.open(cover_path).convert("RGB")
    available = capacity_bytes(*image.size)
    if len(frame) > available:
        raise StegoError(f"Cover too small: need {len(frame)} bytes, have {available}")

    pixels = list(image.getdata())
    bit_iter = _bits(frame)
    out_pixels = []
    exhausted = False
    for pixel in pixels:
        channels = list(pixel)
        for channel in range(3):
            if not exhausted:
                try:
                    channels[channel] = (channels[channel] & 0xFE) | next(bit_iter)
                except StopIteration:
                    exhausted = True
        out_pixels.append(tuple(channels))

    image.putdata(out_pixels)
    out_path = Path(output).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG")
    return {
        "output": str(out_path),
        "payload_bytes": len(raw),
        "capacity_bytes": available,
        "encrypted": bool(key),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def extract(image: str | Path, key: Optional[str] = None) -> dict:
    """Recover an embedded payload from a stego image."""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise StegoError("Pillow is required: pip install pillow") from exc

    path = Path(image).expanduser()
    if not path.exists():
        raise StegoError(f"Image not found: {path}")

    image = Image.open(path).convert("RGB")
    bits = []
    for pixel in image.getdata():
        for channel in pixel[:3]:
            bits.append(channel & 1)

    def take(count: int) -> bytes:
        needed = count * 8
        if needed > len(bits):
            raise StegoError("Frame truncated")
        value = 0
        for bit in bits[:needed]:
            value = (value << 1) | bit
        del bits[:needed]
        return value.to_bytes(count, "big")

    if take(len(MAGIC)) != MAGIC:
        raise StegoError("No PGST frame found")
    if take(1)[0] != VERSION:
        raise StegoError("Unsupported frame version")
    checksum = take(4)
    length = struct.unpack(">I", take(4))[0]
    body = take(length)

    if hashlib.sha256(body).digest()[:4] != checksum:
        raise StegoError("Checksum mismatch (wrong key or re-encoded lossily)")

    data = _xor(body, key)
    try:
        text = data.decode()
    except UnicodeDecodeError:
        text = None
    return {
        "image": str(path),
        "length": length,
        "encrypted": bool(key),
        "payload": text,
        "bytes": data.hex() if text is None else None,
    }


__all__ = ["StegoError", "capacity_bytes", "embed", "extract"]
