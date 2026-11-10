"""Quantum-secure C2 listener.

A small, self-contained command and control channel that carries a session
key derived with a hybrid (classical + post-quantum style) derivation, so the
transport demonstrates the quantum-readiness posture the rest of the module
advertises.

The listener is *local by default*: it binds to loopback unless an explicit
bind address is given, and every session is authenticated with a shared secret.
It is a laboratory component for authorised engagements.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from pegasus.modules.quantum import qsec

STATE_DIR = Path.home() / ".pegasus" / "quantum"
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 4443
PROTOCOL = "pegasus-quantum-c2/1"


def derive_session_key(shared: bytes, salt: bytes = b"") -> bytes:
    """Hybrid HKDF-SHA256 key derivation with a salted context string."""
    return qsec.hybrid_hkdf(shared, salt=salt or b"pegasus-quantum-c2")


class QuantumC2Server:
    """A minimal, authenticated command channel."""

    def __init__(self, host: str = DEFAULT_BIND, port: int = DEFAULT_PORT,
                 secret: Optional[bytes] = None) -> None:
        self.host = host
        self.port = port
        self.secret = secret or os.urandom(32)
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.log: list[Dict[str, Any]] = []
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------ util
    def _record(self, event: str, **extra) -> None:
        entry = {"event": event, "at": time.time(), **extra}
        self.log.append(entry)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "c2-log.jsonl").open("a", encoding="utf-8").write(
            json.dumps(entry) + "\n")

    def public_descriptor(self) -> Dict[str, Any]:
        """Non-secret description of this listener."""
        return {
            "protocol": PROTOCOL,
            "bind": f"{self.host}:{self.port}",
            "loopback_only": self.host in ("127.0.0.1", "::1", "localhost"),
            "sessions": len(self.sessions),
            "fingerprint": hashlib.sha256(self.secret).hexdigest()[:16],
            "key_algorithm": "HKDF-SHA256 hybrid",
        }

    def _authenticate(self, presented: bytes) -> Optional[str]:
        expected = derive_session_key(self.secret, b"auth")
        if not hmac.compare_digest(expected, presented):
            return None
        return secrets.token_hex(8)

    # --------------------------------------------------------------- runtime
    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(30)
        try:
            raw = conn.recv(4096)
            if not raw:
                return
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._record("malformed")
                return
            token = self._authenticate(bytes.fromhex(str(payload.get("key", ""))))
            if not token:
                self._record("auth-failed", remote=payload.get("id"))
                conn.sendall(json.dumps({"ok": False, "error": "auth"}).encode())
                return
            session_id = payload.get("id") or token
            self.sessions[session_id] = {
                "id": session_id, "joined": time.time(),
                "agent": payload.get("agent") or "unknown",
            }
            self._record("session-open", session=session_id,
                         agent=payload.get("agent"))
            conn.sendall(json.dumps({
                "ok": True, "session": session_id, "protocol": PROTOCOL,
                "server_time": time.time(),
            }).encode())
        except Exception as exc:  # noqa: BLE001
            self._record("error", detail=str(exc)[:200])
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def start(self) -> Dict[str, Any]:
        if self._server is not None:
            return self.public_descriptor()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(16)
        server.settimeout(0.5)
        self._server = server
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    conn, _addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        self._record("listener-start", bind=f"{self.host}:{self.port}")
        return self.public_descriptor()

    def stop(self) -> Dict[str, Any]:
        self._stop.set()
        if self._server is not None:
            try:
                self._server.close()
            except Exception:
                pass
            self._server = None
        self._record("listener-stop")
        return {"stopped": True, "sessions": len(self.sessions)}

    def status(self) -> Dict[str, Any]:
        return {**self.public_descriptor(), "running": self._server is not None,
                "recent": self.log[-10:]}


def probe(host: str = DEFAULT_BIND, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """Check whether a quantum C2 listener answers on the given address."""
    try:
        with socket.create_connection((host, port), timeout=3) as sock:
            sock.sendall(json.dumps({"id": "probe", "key": ""}).encode())
            data = sock.recv(1024)
        return {"reachable": True, "response": data.decode("utf-8", "replace")[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"reachable": False, "error": str(exc)[:160]}
