"""Wallet profile routes.

Wallet profiles are *watch-only* records: an address, a chain and optional
public metadata.  Nothing in this module signs a transaction, holds a private
key, discovers wallet files on disk, or performs credential recovery.  Balance
lookups use public block explorers and degrade to "unknown" when the network
or an API key is unavailable.
"""
from __future__ import annotations

import json
import pathlib
import time
from typing import Any, Dict, List
from urllib import request as urlrequest

from flask import request

from pegasus.modules.auth import operator

WALLET_FILE = pathlib.Path.home() / ".pegasus" / "wallets.json"

CHAINS: Dict[str, Dict[str, Any]] = {
    "BTC": {"name": "Bitcoin", "symbol": "BTC", "decimals": 8,
            "explorer": "https://blockstream.info/api/address"},
    "ETH": {"name": "Ethereum", "symbol": "ETH", "decimals": 18,
            "explorer": "https://api.blockcypher.com/v1/eth/main/addrs"},
    "DOGE": {"name": "Dogecoin", "symbol": "DOGE", "decimals": 8,
             "explorer": "https://api.blockcypher.com/v1/doge/main/addrs"},
    "XRP": {"name": "XRP", "symbol": "XRP", "decimals": 6,
            "explorer": "https://xrpscan.com"},
    "LTC": {"name": "Litecoin", "symbol": "LTC", "decimals": 8,
            "explorer": "https://api.blockcypher.com/v1/ltc/main/addrs"},
    "USDC": {"name": "USD Coin", "symbol": "USDC", "decimals": 6,
             "explorer": "https://api.blockcypher.com/v1/eth/main/addrs"},
    "USDT": {"name": "Tether", "symbol": "USDT", "decimals": 6,
             "explorer": "https://api.blockcypher.com/v1/eth/main/addrs"},
}

ADDRESS_HINTS = {
    "BTC": (r"^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,87}$",),
    "ETH": (r"^0x[a-fA-F0-9]{40}$",),
    "DOGE": (r"^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$",),
    "XRP": (r"^r[0-9A-Za-z]{24,34}$",),
    "LTC": (r"^(ltc1|[LM3])[a-zA-HJ-NP-Z0-9]{25,87}$",),
    "USDC": (r"^0x[a-fA-F0-9]{40}$",),
    "USDT": (r"^0x[a-fA-F0-9]{40}$",),
}


def _read() -> Dict[str, Any]:
    try:
        return json.loads(WALLET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: Dict[str, Any]) -> None:
    WALLET_FILE.parent.mkdir(parents=True, exist_ok=True)
    WALLET_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _valid(chain: str, address: str) -> bool:
    import re
    hints = ADDRESS_HINTS.get(chain, ())
    return any(re.match(pattern, address) for pattern in hints)


def _balance(chain: str, address: str) -> Dict[str, Any]:
    """Best-effort public balance lookup; never raises."""
    out: Dict[str, Any] = {"chain": chain, "address": address, "balance": None,
                           "symbol": CHAINS.get(chain, {}).get("symbol"),
                           "source": "offline"}
    if chain == "BTC":
        url = f"https://blockstream.info/api/address/{address}"
        try:
            with urlrequest.urlopen(url, timeout=6) as resp:
                data = json.loads(resp.read().decode())
            funded = sum(tx.get("value", 0) for tx in data.get("chain_stats", {})
                         if tx.get("status") == "confirmed")
            out["balance"] = funded / 1e8
            out["source"] = "blockstream.info"
            out["tx_count"] = data.get("chain_stats", {}).get("tx_count")
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)[:160]
        return out
    for key in ("balance", "unconfirmed_balance", "tx_count"):
        out[key] = None
    return out


def register(app, ok, fail):
    @app.get("/api/wallets/chains")
    @operator.require("viewer")
    def wallet_chains():
        return ok({"chains": [
            {"id": cid, "name": meta["name"], "symbol": meta["symbol"],
             "decimals": meta["decimals"]} for cid, meta in CHAINS.items()]})

    @app.get("/api/wallets")
    @operator.require("viewer")
    def wallet_list():
        op = operator.current()
        store = _read()
        items = store.get(op["user"], [])
        return ok({"wallets": items})

    @app.post("/api/wallets")
    @operator.require("operator")
    def wallet_create():
        op = operator.current()
        body = request.get_json(silent=True) or {}
        chain = (body.get("chain") or "").upper()
        address = (body.get("address") or "").strip()
        if chain not in CHAINS:
            return fail("unsupported chain", 400)
        if not address:
            return fail("address required")
        if not _valid(chain, address):
            return fail(f"address does not look like a {chain} address", 400)
        store = _read()
        items = store.setdefault(op["user"], [])
        for item in items:
            if item.get("chain") == chain and item.get("address") == address:
                return fail("wallet already tracked", 409)
        entry = {"id": len(items) + 1, "chain": chain, "address": address,
                 "label": body.get("label") or f"{chain} {len(items) + 1}",
                 "notes": body.get("notes") or "",
                 "watch_only": True, "created": time.time()}
        items.append(entry)
        _write(store)
        return ok({"wallet": entry})

    @app.patch("/api/wallets/<int:wallet_id>")
    @operator.require("operator")
    def wallet_update(wallet_id: int):
        op = operator.current()
        body = request.get_json(silent=True) or {}
        store = _read()
        items = store.get(op["user"], [])
        target = next((i for i in items if i.get("id") == wallet_id), None)
        if not target:
            return fail("wallet not found", 404)
        for key in ("label", "notes"):
            if key in body:
                target[key] = body[key]
        _write(store)
        return ok({"wallet": target})

    @app.delete("/api/wallets/<int:wallet_id>")
    @operator.require("operator")
    def wallet_delete(wallet_id: int):
        op = operator.current()
        store = _read()
        items = store.get(op["user"], [])
        before = len(items)
        items[:] = [i for i in items if i.get("id") != wallet_id]
        if len(items) == before:
            return fail("wallet not found", 404)
        _write(store)
        return ok({"deleted": True})

    @app.get("/api/wallets/<int:wallet_id>/balance")
    @operator.require("viewer")
    def wallet_balance(wallet_id: int):
        op = operator.current()
        store = _read()
        items = store.get(op["user"], [])
        target = next((i for i in items if i.get("id") == wallet_id), None)
        if not target:
            return fail("wallet not found", 404)
        return ok({"balance": _balance(target["chain"], target["address"])})
