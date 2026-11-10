"""Blockchain integration module (Phase 23) - contract reads, Merkle proofs, CAS, token ledger."""
from __future__ import annotations

import json

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import HookType

from pegasus.modules.blockchain import chain


class BlockchainModule(BaseModule):
    """Read-only chain interaction, proofs, storage, and ledger tooling."""

    @property
    def module_name(self) -> str:
        return "Blockchain Integration"

    @property
    def module_description(self) -> str:
        return "Smart contract interaction, decentralized storage, cryptographic proof, token economy"

    @property
    def module_category(self) -> str:
        return "intelligence"

    async def _register_commands(self) -> None:
        self.register_command("bc-balance", "Read an ERC-20 balance via JSON-RPC eth_call", self.cmd_balance)
        self.register_command("bc-encode-transfer", "Encode an ERC-20 transfer calldata payload", self.cmd_encode_transfer)
        self.register_command("bc-merkle", "Build a SHA-256 Merkle tree and inclusion proof", self.cmd_merkle)
        self.register_command("bc-cas-put", "Store content in the content-addressed store", self.cmd_cas_put)
        self.register_command("bc-cas-stats", "Show content-addressed store stats", self.cmd_cas_stats)
        self.register_command("bc-ledger", "Token ledger: balance|mint|transfer|quota", self.cmd_ledger)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="blockchain_dashboard",
            component_type="panel",
            path="/blockchain",
            title="Blockchain Dashboard",
            icon="link",
            order=13,
        )

    async def _register_hooks(self) -> None:
        pass

    async def cmd_balance(self, *args) -> None:
        if len(args) >= 3:
            endpoint, token, holder = args[0], args[1], args[2]
        else:
            endpoint = self.prompt("JSON-RPC endpoint", default="https://mainnet.infura.io/v3/<key>") or "https://mainnet.infura.io/v3/<key>"
            token = self.prompt("ERC-20 contract address", default="") or ""
            holder = self.prompt("Holder address", default="") or ""
        if not endpoint or not token or not holder:
            self.print_error("endpoint, token and holder are required")
            return
        try:
            wei = chain.erc20_balance(endpoint, token, holder)
            self.print_success(json.dumps({"holder": holder, "token": token, "balance_wei": wei}))
        except Exception as exc:
            self.print_error(f"eth_call failed: {exc}")

    async def cmd_encode_transfer(self, *args) -> None:
        if len(args) >= 2:
            address, amount = args[0], int(args[1])
        else:
            address = self.prompt("Recipient address", default="") or ""
            amount = int(self.prompt("Amount (wei)", default="0") or "0")
        print(chain.encode_transfer(address, amount))

    async def cmd_merkle(self, *args) -> None:
        raw = " ".join(str(a) for a in args) or (self.prompt("Leaves (space separated)", default="alpha beta gamma") or "")
        leaves = [t.encode() for t in raw.split() if t]
        tree = chain.MerkleTree(leaves)
        proof = tree.proof(0)
        print(json.dumps({
            "root": tree.root.hex(),
            "leaves": [x.decode() for x in leaves],
            "proof_for_leaf_0": proof,
            "verify": chain.MerkleTree.verify(leaves[0], proof, tree.root.hex()) if leaves else True,
        }, indent=2))

    async def cmd_cas_put(self, *args) -> None:
        content = " ".join(str(a) for a in args) or (self.prompt("Content to store", default="pegasus") or "pegasus")
        cid = chain.ContentAddressedStore().put(content.encode("utf-8"))
        self.print_success(f"stored as {cid}")

    async def cmd_cas_stats(self, *args) -> None:
        print(json.dumps(chain.ContentAddressedStore().stats(), indent=2))

    async def cmd_ledger(self, *args) -> None:
        ledger = chain.TokenLedger()
        action = (str(args[0]) if args else (self.prompt("action (balance|mint|transfer|quota)", default="balance") or "balance")).lower()
        if action == "balance":
            name = (args[1] if len(args) > 1 else self.prompt("account", default="default")) or "default"
            print(json.dumps({"account": name, "balance": ledger.balance(name), "info": ledger.account(name)}))
        elif action == "mint":
            name = (args[1] if len(args) > 1 else self.prompt("account", default="default")) or "default"
            amount = int(args[2] if len(args) > 2 else (self.prompt("amount", default="100") or "100"))
            print(json.dumps(ledger.mint(name, amount, "manual-grant")))
        elif action == "transfer":
            src = (args[1] if len(args) > 1 else self.prompt("source account", default="default")) or "default"
            dst = (args[2] if len(args) > 2 else self.prompt("destination account", default="tenant-b")) or "tenant-b"
            amount = int(args[3] if len(args) > 3 else (self.prompt("amount", default="10") or "10"))
            print(json.dumps(ledger.transfer(src, dst, amount)))
        elif action == "quota":
            name = (args[1] if len(args) > 1 else self.prompt("account", default="default")) or "default"
            quota = int(args[2] if len(args) > 2 else (self.prompt("quota", default="1000") or "1000"))
            ledger.set_quota(name, quota)
            print(json.dumps({"account": name, "quota": quota}))
        else:
            self.print_error(f"unknown ledger action: {action}")
