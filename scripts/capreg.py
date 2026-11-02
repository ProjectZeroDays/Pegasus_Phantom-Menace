#!/usr/bin/env python3
"""Single source of truth for the cap enum and the transport provider map.

Both modules_lint and caps_matrix import this. Neither parses core/caps.py
itself, so they cannot disagree about what a cap is — the shared module is the
agreement, not a convention.

AST, not regex: a docstring edit, a reformat, or a second enum cannot silently
change the parsed set. Parsing also proves the file is valid Python.

Exit conventions the lints share: 0 clean, 2 violation, 3 precondition.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

CAPS = Path("core/caps.py")
REGISTRY = Path("transports/registry.yaml")
ALLOW = Path("build/caps_orphans.allow")
BASELINE = Path("build/caps_baseline.json")
ENUM = "Cap"


class Precondition(Exception):
    """The tree is not shaped as expected; exit 3, not 2."""


def cap_values(caps: Path = CAPS) -> list[str]:
    """Every Cap member value, in declaration order."""
    if not caps.exists():
        raise Precondition(f"{caps} missing")
    tree = ast.parse(caps.read_text(encoding="utf-8"), filename=str(caps))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == ENUM:
            out = []
            for stmt in node.body:
                if (isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, str)):
                    out.append(stmt.value.value)
            if not out:
                raise Precondition(f"{ENUM} in {caps} has no string members")
            return out
    raise Precondition(f"no class {ENUM} in {caps}")


def providers(registry: Path = REGISTRY) -> dict[str, list[str]]:
    """cap value -> transport names advertising it."""
    if not registry.exists():
        raise Precondition(f"{registry} missing")
    import yaml
    rows = yaml.safe_load(registry.read_text(encoding="utf-8")) or []
    if not isinstance(rows, list) or not rows:
        raise Precondition(f"{registry} has no transports")
    out: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise Precondition(f"{registry} has a non-mapping row")
        name = row.get("name", "?")
        for cap in row.get("provides") or []:
            out.setdefault(cap, []).append(name)
    return out


def allowlist(path: Path = ALLOW) -> dict[str, str]:
    """cap value -> reason. Blank lines and # comments ignored."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        head, _, tail = line.partition("#")
        cap = head.strip()
        if cap:
            out[cap] = tail.strip()
    return out


def split_orphans(values, provided, allowed):
    """(blocking, waived). Waiving an absent cap is itself reported."""
    orphans = [c for c in values if c not in provided]
    waived = [c for c in orphans if c in allowed]
    blocking = [c for c in orphans if c not in allowed]
    stale = sorted(c for c in allowed if c not in orphans)
    return blocking, waived, stale


def phantom_provides(values, provided) -> list[str]:
    """Caps a transport advertises but the enum does not define — a typo."""
    known = set(values)
    return sorted(c for c in provided if c not in known)


def load_baseline(path: Path = BASELINE) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_baseline(provided, path: Path = BASELINE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: len(v) for k, v in sorted(provided.items())}, indent=2) + "\n",
        encoding="utf-8")


def dropped_edges(baseline, provided) -> list[str]:
    """Caps whose provider count fell since the baseline was taken."""
    return sorted(c for c, n in baseline.items() if len(provided.get(c, [])) < n)
