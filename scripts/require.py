#!/usr/bin/env python3
"""Phase precondition checker. Exit 3 on absence or drift. --lint validates."""
import hashlib, sys
from pathlib import Path
import yaml

PHASES = Path("build/phases.yaml")
REQUIRED = {"id", "gate", "revert"}
GATES = {f"G{i}" for i in range(1, 25)}


def die(msg, code=3):
    print(f"PRECONDITION: {msg}", file=sys.stderr)
    sys.exit(code)


def load():
    if not PHASES.exists():
        die(f"{PHASES} missing")
    data = yaml.safe_load(PHASES.read_text(encoding="utf-8")) or {}
    phases = data.get("phases")
    if not isinstance(phases, list) or not phases:
        die("phases.yaml has no phases list")
    return phases


def lint(phases):
    ids = [p.get("id") for p in phases]
    if len(ids) != len(set(ids)):
        die("duplicate phase id")
    for p in phases:
        missing = REQUIRED - set(p)
        if missing:
            die(f"{p.get('id', '?')}: missing {sorted(missing)}")
        if p["gate"] not in GATES:
            die(f"{p['id']}: unknown gate {p['gate']}")
        produces = {x if isinstance(x, str) else x["path"] for x in p.get("produces", [])}
        requires = {x["path"] for x in p.get("requires", [])}
        if produces & requires:
            die(f"{p['id']}: requires what it produces")
        if p["id"] != "P0" and "docs/HANDOFF.md" not in requires:
            die(f"{p['id']}: must require docs/HANDOFF.md")
    order = {pid: i for i, pid in enumerate(ids)}
    if "P8" not in order:
        die("P8 missing")
    for pid in ids:
        if pid.startswith("R") and order[pid] < order["P8"]:
            die(f"{pid}: R-phase before P8")
    print(f"phases.yaml valid ({len(ids)} phases)")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(phase_id):
    phases = {p["id"]: p for p in load()}
    if phase_id not in phases:
        die(f"unknown phase {phase_id}")
    ph = phases[phase_id]
    for req in ph.get("requires", []):
        path = Path(req["path"])
        if not path.exists():
            die(f"{phase_id} requires {path}")
        if req.get("sha256") and sha(path) != req["sha256"]:
            die(f"{path} drifted since {phase_id} was planned")
    for entry in ph.get("requires_empty", []):
        p = Path(entry)
        if p.is_file() and p.stat().st_size:
            die(f"{entry} must be empty before {phase_id}")
        if p.is_dir() and any(p.iterdir()):
            die(f"{entry} must be empty before {phase_id}")
    print(f"{phase_id}: preconditions satisfied")


if __name__ == "__main__":
    if "--lint" in sys.argv:
        lint(load())
    elif len(sys.argv) > 1:
        check(sys.argv[1])
    else:
        die("usage: require.py <phase> | --lint")
