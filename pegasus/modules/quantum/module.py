"""Quantum security module (Phase 24) - QKD simulation, PQC audit, hash-based signatures."""
from __future__ import annotations

import json
from pathlib import Path

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import HookType

from pegasus.modules.quantum import qsec


class QuantumModule(BaseModule):
    """Quantum-readiness toolkit: simulation, migration audit, hash-based signatures."""

    @property
    def module_name(self) -> str:
        return "Quantum Security"

    @property
    def module_description(self) -> str:
        return "Quantum cryptography, QKD simulation, post-quantum migration audit, quantum-resistant checks"

    @property
    def module_category(self) -> str:
        return "security"

    async def _register_commands(self) -> None:
        self.register_command("q-bb84", "Simulate BB84 QKD with optional Eve (detection demo)", self.cmd_bb84)
        self.register_command("q-hybrid-key", "Derive 256-bit key from shared material (HKDF-SHA256)", self.cmd_hybrid_key)
        self.register_command("q-pqc-audit", "Scan a tree for quantum-vulnerable crypto; emit NIST PQC report", self.cmd_pqc_audit)
        self.register_command("q-resistant-check", "Evaluate current config against quantum-resistant baseline", self.cmd_resistant_check)
        self.register_command("q-lamport-demo", "Generate Lamport one-time keypair, sign, verify (single use)", self.cmd_lamport_demo)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="quantum_dashboard",
            component_type="panel",
            path="/quantum",
            title="Quantum Security Dashboard",
            icon="atom",
            order=14,
        )

    async def _register_hooks(self) -> None:
        pass

    async def cmd_bb84(self, *args) -> None:
        n = int(args[0]) if args and str(args[0]).isdigit() else 512
        eve = len(args) > 1 and str(args[1]).lower() in {"eve", "y", "yes", "true", "1"}
        print(json.dumps(qsec.bb84_simulate(n, 0.0, eve), indent=2))

    async def cmd_hybrid_key(self, *args) -> None:
        raw = str(args[0]) if args else (self.prompt("Shared secret (hex or text)", default="pegasus-shared-secret") or "pegasus-shared-secret")
        secret = bytes.fromhex(raw) if all(c in "0123456789abcdefABCDEF" for c in raw) and len(raw) % 2 == 0 else raw.encode()
        print("derived_key_sha256_hkdf:", qsec.hybrid_hkdf(secret).hex())

    async def cmd_pqc_audit(self, *args) -> None:
        root = Path(args[0]) if args else Path(self.prompt("Tree to scan", default=str(Path.cwd())) or Path.cwd())
        if not root.exists():
            self.print_error(f"no such path: {root}")
            return
        report = qsec.PQCAudit(root).scan()
        print(json.dumps({"summary": report["summary"], "findings": len(report["findings"]), "report": str(qsec.DATA_DIR / "pqc_audit.json")}, indent=2))
        for f in report["findings"][:15]:
            self.print_warning(f"{f['severity'].upper():6} {f['file']}:{f['line']} {f['issue']} -> {f['recommendation']}")

    async def cmd_resistant_check(self, *args) -> None:
        print(json.dumps(qsec.quantum_resistant_check(), indent=2))

    async def cmd_lamport_demo(self, *args) -> None:
        keypair = qsec.LamportOneTime.generate()
        message = (args[0] if args else "pegasus-quantum-demo").encode()
        signature = qsec.LamportOneTime.sign(keypair["private"], message)
        ok = qsec.LamportOneTime.verify(keypair["public"], message, signature)
        print(json.dumps({
            "message": message.decode(),
            "signature_values": len(signature),
            "verify": ok,
            "note": "EXPERIMENTAL Lamport OTS: this keypair is now burned; never sign another message with it.",
        }, indent=2))
