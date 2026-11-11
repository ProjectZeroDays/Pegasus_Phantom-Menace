"""MSGRPC client for the Metasploit Framework RPC daemon.

The daemon (``lib/msf/core/rpc/v10/service.rb``) serves the classic
"Msg" service over an HTTP server with TLS enabled by default:

* ``POST /uri``
* ``Content-Type: binary/message-pack``
* the body is a MessagePack **array**: ``["auth.login", user, pass]``
* the reply is a MessagePack map: ``{"result": "success", "token": "..."}``

The daemon resets the connection when the framing is wrong, so this module
sends exactly that and falls back to plain HTTP for daemons started without
SSL.
"""
from __future__ import annotations

import ssl
import struct
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - depends on the host
    import msgpack as _msgpack
except Exception:  # pragma: no cover
    _msgpack = None

CONTENT_TYPE = "binary/message-pack"
URIS = ("/api/", "/uri", "/msfapi", "/")


# ---------------------------------------------------------------------------
# MessagePack - a small subset covering str, bool, int, None, list and map
# ---------------------------------------------------------------------------

def _pack(value: Any) -> bytes:
    if _msgpack is not None:
        return _msgpack.packb(value, use_bin_type=True)
    out = bytearray()
    _pack_into(value, out)
    return bytes(out)


def _pack_into(value: Any, out: bytearray) -> None:
    if value is None:
        out.append(0xC0)
    elif isinstance(value, bool):
        out.append(0xC3 if value else 0xC2)
    elif isinstance(value, int):
        if 0 <= value < 128:
            out.append(value)
        elif -32 <= value < 0:
            out.append(0xE0 | (value + 32))
        elif 0 <= value < 256:
            out.append(0xCC)
            out.append(value)
        elif 0 <= value < 65536:
            out.append(0xCD)
            out += struct.pack(">H", value)
        else:
            out.append(0xCE)
            out += struct.pack(">I", value)
    elif isinstance(value, float):
        out.append(0xCB)
        out += struct.pack(">d", value)
    elif isinstance(value, str):
        blob = value.encode("utf-8")
        if len(blob) < 32:
            out.append(0xA0 | len(blob))
        elif len(blob) < 256:
            out.append(0xD9)
            out.append(len(blob))
        else:
            out.append(0xDA)
            out += struct.pack(">H", len(blob))
        out += blob
    elif isinstance(value, (list, tuple)):
        if len(value) < 16:
            out.append(0x90 | len(value))
        else:
            out.append(0xDC)
            out += struct.pack(">H", len(value))
        for item in value:
            _pack_into(item, out)
    elif isinstance(value, dict):
        if len(value) < 16:
            out.append(0x80 | len(value))
        else:
            out.append(0xDE)
            out += struct.pack(">H", len(value))
        for key, item in value.items():
            _pack_into(key, out)
            _pack_into(item, out)
    else:
        _pack_into(str(value), out)


def _unpack(blob: bytes) -> Any:
    if _msgpack is not None:
        return _msgpack.unpackb(blob, raw=False)
    value, _ = _unpack_at(blob, 0)
    return value


def _unpack_at(blob: bytes, pos: int) -> Tuple[Any, int]:
    if _msgpack is not None:
        return _msgpack.unpackb(blob[pos:], raw=False), len(blob)
    code = blob[pos]
    pos += 1
    if code <= 0x7F:
        return code, pos
    if code >= 0xE0:
        return code - 256, pos
    if 0x80 <= code <= 0x8F:
        return _unpack_map(blob, pos, code & 0x0F)
    if 0x90 <= code <= 0x9F:
        return _unpack_array(blob, pos, code & 0x0F)
    if 0xA0 <= code <= 0xBF:
        length = code & 0x1F
        return blob[pos:pos + length].decode("utf-8", "replace"), pos + length
    if code == 0xC0:
        return None, pos
    if code == 0xC2:
        return False, pos
    if code == 0xC3:
        return True, pos
    if code == 0xCC:
        return blob[pos], pos + 1
    if code == 0xCD:
        return struct.unpack_from(">H", blob, pos)[0], pos + 2
    if code == 0xCE:
        return struct.unpack_from(">I", blob, pos)[0], pos + 4
    if code == 0xCF:
        return struct.unpack_from(">Q", blob, pos)[0], pos + 8
    if code == 0xD9:
        length = blob[pos]
        pos += 1
        return blob[pos:pos + length].decode("utf-8", "replace"), pos + length
    if code == 0xDA:
        length = struct.unpack_from(">H", blob, pos)[0]
        pos += 2
        return blob[pos:pos + length].decode("utf-8", "replace"), pos + length
    if code == 0xDB:
        length = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        return blob[pos:pos + length].decode("utf-8", "replace"), pos + length
    if code == 0xC4:
        length = blob[pos]
        pos += 1
        return blob[pos:pos + length], pos + length
    if code == 0xC5:
        length = struct.unpack_from(">H", blob, pos)[0]
        pos += 2
        return blob[pos:pos + length], pos + length
    if code == 0xC6:
        length = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        return blob[pos:pos + length], pos + length
    if code == 0xDC:
        count = struct.unpack_from(">H", blob, pos)[0]
        pos += 2
        return _unpack_array(blob, pos, count)
    if code == 0xDD:
        count = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        return _unpack_array(blob, pos, count)
    if code == 0xDE:
        count = struct.unpack_from(">H", blob, pos)[0]
        pos += 2
        return _unpack_map(blob, pos, count)
    if code == 0xDF:
        count = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        return _unpack_map(blob, pos, count)
    return None, pos


def _unpack_map(blob: bytes, pos: int, count: int) -> Tuple[Any, int]:
    result = {}
    for _ in range(count):
        key, pos = _unpack_at(blob, pos)
        value, pos = _unpack_at(blob, pos)
        result[key] = value
    return result, pos


def _unpack_array(blob: bytes, pos: int, count: int) -> Tuple[Any, int]:
    items = []
    for _ in range(count):
        value, pos = _unpack_at(blob, pos)
        items.append(value)
    return items, pos



def _normalise(value: Any) -> Any:
    """Metasploit packs some keys and values as MessagePack binary."""
    if isinstance(value, dict):
        return {(_normalise(k)): (_normalise(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return value
    return value

# ---------------------------------------------------------------------------
# the client
# ---------------------------------------------------------------------------

def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def login(host: str = "127.0.0.1", port: int = 55553,
          user: str = "msf", password: str = "", timeout: float = 10.0,
          uris: Optional[List[str]] = None) -> Dict[str, Any]:
    """Perform an MSGRPC auth.login_noauth handshake.

    Returns ``{"ok": bool, "token": str, "error": str}``.
    """
    body = _pack(["auth.login", user, password])
    last_error = ""
    for scheme in ("https", "http"):
        for uri in (uris or list(URIS)):
            url = f"{scheme}://{host}:{int(port)}{uri}"
            request = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": CONTENT_TYPE,
                         "Accept": "binary/message-pack"})
            try:
                if scheme == "https":
                    with urllib.request.urlopen(request, timeout=timeout,
                                                context=_tls_context()) as resp:
                        raw = resp.read()
                else:
                    with urllib.request.urlopen(request, timeout=timeout) as resp:
                        raw = resp.read()
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code} on {url}"
                continue
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__} on {url}: {exc}"
                continue
            try:
                payload = _normalise(_unpack(raw))
            except Exception as exc:  # noqa: BLE001
                last_error = f"undecodable reply from {url}: {exc}"
                continue
            if isinstance(payload, dict) and payload.get("error"):
                return {"ok": False, "token": "", "error": str(payload.get("error"))[:200],
                        "endpoint": url}
            token = ""
            if isinstance(payload, dict):
                token = str(payload.get("token") or "")
            return {"ok": bool(token), "token": token, "error": "",
                    "endpoint": url,
                    "result": payload.get("result") if isinstance(payload, dict) else None}
    return {"ok": False, "token": "", "error": last_error}
