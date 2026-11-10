"""
Pegasus blockchain toolkit (Phase 23).

Honest scope:
- Read-only smart-contract interaction over raw JSON-RPC (eth_call). Writing
  to a chain requires an operator-supplied signer and is deliberately NOT
  automated.
- Merkle inclusion proofs (stdlib hashlib, SHA-256).
- Content-addressed object storage (SHA-256). When an IPFS HTTP API is
  reachable at the configured endpoint, objects are also pinned there.
- Local token ledger + quota bookkeeping for the multi-tenant plane
  (no real funds; an accounting tool, not a chain).
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path.home() / ".pegasus"
LEDGER_PATH = DATA_DIR / "token_ledger.json"
OBJECTS_DIR = DATA_DIR / "objects"

# Well-known ERC-20 function selectors (first 4 bytes of keccak256(signature)).
SEL_BALANCEOF = "70a08231"
SEL_TRANSFER = "a9059cbb"


def _pad32(hex_str: str) -> str:
    return hex_str.lower().removeprefix("0x").rjust(64, "0")


def encode_balanceof(address: str) -> str:
    return "0x" + SEL_BALANCEOF + _pad32(address)


def encode_transfer(address: str, amount_wei: int) -> str:
    return "0x" + SEL_TRANSFER + _pad32(address) + _pad32(hex(int(amount_wei)))


def decode_uint256(hex_data: str) -> int:
    h = hex_data.removeprefix("0x") or "0"
    return int(h, 16)


def rpc_call(endpoint: str, method: str, params: List[Any], timeout: int = 10) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": int(time.time()), "method": method, "params": params}).encode()
    req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
    if "error" in body:
        raise RuntimeError(body["error"])
    return body.get("result")


def eth_call(endpoint: str, to_addr: str, data: str, block: str = "latest") -> str:
    return rpc_call(endpoint, "eth_call", [{"to": to_addr, "data": data}, block])


def erc20_balance(endpoint: str, token: str, holder: str) -> int:
    raw = eth_call(endpoint, token, encode_balanceof(holder))
    return decode_uint256(raw or "0x0")


class MerkleTree:
    """SHA-256 Merkle tree with inclusion proofs."""

    def __init__(self, leaves: List[bytes]) -> None:
        self.leaves = [hashlib.sha256(x).digest() for x in leaves] or [hashlib.sha256(b"").digest()]
        self.root = self._build(list(self.leaves))

    @staticmethod
    def _combine(a: bytes, b: bytes) -> bytes:
        return hashlib.sha256(a + b).digest()

    def _build(self, level: List[bytes]) -> bytes:
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                nxt.append(self._combine(left, right))
            level = nxt
        return level[0]

    def proof(self, index: int) -> List[Dict[str, str]]:
        level = list(self.leaves)
        path: List[Dict[str, str]] = []
        idx = index
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                nxt.append(self._combine(left, right))
            sibling = idx ^ 1
            if sibling < len(level):
                path.append({"position": "right" if idx % 2 == 0 else "left", "hash": level[sibling].hex()})
            idx //= 2
            level = nxt
        return path

    @staticmethod
    def verify(leaf: bytes, proof: List[Dict[str, str]], root_hex: str) -> bool:
        h = hashlib.sha256(leaf).digest()
        for step in proof:
            sib = bytes.fromhex(step["hash"])
            h = hashlib.sha256(h + sib).digest() if step["position"] == "right" else hashlib.sha256(sib + h).digest()
        return h.hex() == root_hex


class ContentAddressedStore:
    """SHA-256 content-addressed object store; pins to IPFS when reachable."""

    def __init__(self, root: Path = OBJECTS_DIR, ipfs_api: Optional[str] = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.ipfs_api = (ipfs_api or "http://127.0.0.1:5001/api/v0").rstrip("/")

    def put(self, content: bytes) -> str:
        cid = hashlib.sha256(content).hexdigest()
        dest = self.root / cid[:2] / cid
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(content)
        return cid

    def get(self, cid: str) -> Optional[bytes]:
        path = self.root / cid[:2] / cid
        return path.read_bytes() if path.exists() else None

    def stats(self) -> Dict[str, Any]:
        files = list(self.root.rglob("*"))
        blobs = [p for p in files if p.is_file()]
        return {"objects": len(blobs), "bytes": sum(p.stat().st_size for p in blobs), "root": str(self.root)}

    def pin_to_ipfs(self, cid: str) -> Dict[str, Any]:
        data = self.get(cid)
        if data is None:
            return {"ok": False, "error": "object not stored locally"}
        try:
            body = b"--pegasusboundary\r\nContent-Disposition: form-data; name=\"file\"\r\n\r\n" + data + b"\r\n--pegasusboundary--\r\n"
            req = urllib.request.Request(
                f"{self.ipfs_api}/add",
                data=body,
                headers={"Content-Type": "multipart/form-data; boundary=pegasusboundary"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                out = json.loads(resp.read().decode("utf-8", errors="replace").splitlines()[0])
            return {"ok": True, "ipfs_hash": out.get("Hash"), "cid": cid}
        except Exception as exc:  # unreachable / daemon down - report honestly
            return {"ok": False, "cid": cid, "error": f"IPFS API not reachable at {self.ipfs_api}: {exc}"}


class TokenLedger:
    """Local multi-tenant token ledger and quota tracker (not a chain)."""

    def __init__(self, path: Path = LEDGER_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"accounts": {}, "audit": []}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def balance(self, account: str) -> int:
        return int(self._state["accounts"].get(account, {}).get("balance", 0))

    def _txn(self, account: str, delta: int, reason: str) -> Dict[str, Any]:
        acct = self._state["accounts"].setdefault(account, {"balance": 0, "quota": 0})
        acct["balance"] = int(acct["balance"]) + delta
        entry = {"ts": time.time(), "account": account, "delta": delta, "reason": reason}
        self._state["audit"] = (self._state.get("audit", []) + [entry])[-500:]
        self._save()
        return {"account": account, "balance": acct["balance"], "delta": delta, "reason": reason}

    def mint(self, account: str, amount: int, reason: str = "grant") -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("amount must be positive")
        return self._txn(account, int(amount), reason)

    def transfer(self, src: str, dst: str, amount: int) -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("amount must be positive")
        if self.balance(src) < amount:
            raise ValueError("insufficient local balance")
        self._txn(src, -int(amount), f"transfer:{dst}")
        return self._txn(dst, int(amount), f"transfer:{src}")

    def set_quota(self, account: str, quota: int) -> None:
        acct = self._state["accounts"].setdefault(account, {"balance": 0, "quota": 0})
        acct["quota"] = int(quota)
        self._save()

    def account(self, account: str) -> Dict[str, Any]:
        return self._state["accounts"].get(account, {"balance": 0, "quota": 0})
