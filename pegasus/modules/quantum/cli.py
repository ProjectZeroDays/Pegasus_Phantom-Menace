"""Quantum security command line interface.

Usage::

    python -m pegasus.modules.quantum.cli bb84 [--eve]
    python -m pegasus.modules.quantum.cli hybrid-key <secret>
    python -m pegasus.modules.quantum.cli resistant-check
    python -m pegasus.modules.quantum.cli c2 start|stop|status|probe
    python -m pegasus.modules.quantum.cli audit <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from pegasus.modules.quantum import qsec
from pegasus.modules.quantum import c2 as qc2


def _print(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pegasus-quantum",
                                     description="Quantum security toolkit.")
    sub = parser.add_subparsers(dest="command", required=True)

    bb84 = sub.add_parser("bb84", help="simulate BB84 key distribution")
    bb84.add_argument("--bits", type=int, default=512)
    bb84.add_argument("--eve", action="store_true")

    hybrid = sub.add_parser("hybrid-key", help="derive a hybrid session key")
    hybrid.add_argument("secret")

    sub.add_parser("resistant-check", help="quantum resistance baseline")

    audit = sub.add_parser("audit", help="scan a tree for quantum-weak crypto")
    audit.add_argument("path", nargs="?", default=".")

    c2 = sub.add_parser("c2", help="quantum-secure C2 listener")
    c2.add_argument("action", choices=["start", "stop", "status", "probe"])
    c2.add_argument("--host", default=qc2.DEFAULT_BIND)
    c2.add_argument("--port", type=int, default=qc2.DEFAULT_PORT)

    lamport = sub.add_parser("lamport", help="one-time signature demonstration")
    lamport.add_argument("message", nargs="?", default="pegasus-quantum-demo")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "bb84":
        _print(qsec.bb84_simulate(args.bits, 0.0, args.eve))
        return 0
    if args.command == "hybrid-key":
        raw = args.secret
        secret = bytes.fromhex(raw) if all(
            c in "0123456789abcdefABCDEF" for c in raw) and len(raw) % 2 == 0 else raw.encode()
        _print({"key": qsec.hybrid_hkdf(secret).hex()})
        return 0
    if args.command == "resistant-check":
        _print(qsec.quantum_resistant_check())
        return 0
    if args.command == "audit":
        root = Path(args.path)
        if not root.exists():
            print(f"no such path: {root}", file=sys.stderr)
            return 1
        report = qsec.PQCAudit(root).scan()
        _print({"summary": report["summary"], "findings": len(report["findings"])})
        return 0
    if args.command == "lamport":
        keypair = qsec.LamportOneTime.generate()
        message = args.message.encode()
        signature = qsec.LamportOneTime.sign(keypair["private"], message)
        ok = qsec.LamportOneTime.verify(keypair["public"], message, signature)
        _print({"verified": ok, "message": args.message,
                "note": "one-time keypair burned - do not reuse"})
        return 0
    if args.command == "c2":
        if args.action == "probe":
            _print(qc2.probe(args.host, args.port))
            return 0
        server = qc2.QuantumC2Server(host=args.host, port=args.port)
        if args.action == "start":
            _print(server.start())
            return 0
        if args.action == "status":
            _print(server.status())
            return 0
        if args.action == "stop":
            _print(server.stop())
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
