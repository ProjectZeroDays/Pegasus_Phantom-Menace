#!/usr/bin/env python3
"""Verify generated tooling matches .bootstrap-state. Exit 1 on tamper."""
import hashlib, sys
from pathlib import Path

STATE = Path(".bootstrap-state")
if not STATE.exists():
    sys.exit("PRECONDITION: .bootstrap-state missing — run bootstrap")

bad = 0
for line in STATE.read_text().splitlines():
    if not line.strip():
        continue
    want, path = line.split(None, 1)
    p = Path(path)
    if not p.exists():
        print(f"missing: {path}")
        bad = 1
        continue
    if hashlib.sha256(p.read_bytes()).hexdigest() != want:
        print(f"modified: {path}")
        bad = 1
sys.exit(1 if bad else 0)
