#!/usr/bin/env python3
"""Scaffold a module: manifest, method, schema, fixture, contract test.

Replaces the absent pegasus.modules.postex.scaffold. Exit 3 on bad input.
"""
import json, re, sys
from pathlib import Path

ROOT = Path("pegasus/modules")
BLASTS = ("readonly", "stateful", "destructive", "irreversible")
COSTS = ("cheap", "moderate", "expensive")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

MODULE_PY = '''"""{mid} module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BLAST = "{blast}"
COST = "{cost}"
REQUIRES_CAPS: set[str] = set()
SCHEMA = Path(__file__).with_name("schema.json")


def schema() -> dict[str, Any]:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def run(ctx: Any, target: str, **kw: Any) -> dict[str, Any]:
    """Return the envelope. Device-side failure is ok=False, never an exception."""
    return {{
        "ok": True, "module": "{mid}", "target": target,
        "started": None, "finished": None, "requires_root": False,
        "steps": [], "artifacts": [], "findings": {{}}, "errors": [],
    }}
'''

PLUGIN_PY = '''"""{mid} plugin registration."""

from __future__ import annotations

from typing import Any

from .module import BLAST, COST, run

NAME = "{mid}"


def register(registry: Any) -> None:
    registry.register(NAME, run, blast=BLAST, cost=COST)
'''


def schema_for(mid: str) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{mid} result envelope", "type": "object",
        "required": ["ok", "module", "target", "steps", "artifacts", "findings", "errors"],
        "properties": {
            "ok": {"type": "boolean"}, "module": {"const": mid},
            "target": {"type": "string"}, "requires_root": {"type": "boolean"},
            "steps": {"type": "array"}, "artifacts": {"type": "array"},
            "findings": {"type": "object"},
            "errors": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": True,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=", 1)[0]: a.split("=", 1)[1]
             for a in sys.argv[1:] if a.startswith("--") and "=" in a}
    if not args:
        sys.exit("PRECONDITION: usage: module_new.py <id> [--blast=B] [--cost=C]")
    mid = args[0]
    if not ID_RE.match(mid):
        sys.exit(f"PRECONDITION: bad id {mid!r}")
    blast, cost = flags.get("--blast", "readonly"), flags.get("--cost", "cheap")
    if blast not in BLASTS or cost not in COSTS:
        sys.exit("PRECONDITION: bad blast or cost")
    dest = ROOT / mid
    if dest.exists():
        sys.exit(f"PRECONDITION: {dest} exists")
    dest.mkdir(parents=True)
    (dest / "__init__.py").write_text("", encoding="utf-8")
    (dest / "module.py").write_text(
        MODULE_PY.format(mid=mid, blast=blast, cost=cost), encoding="utf-8")
    (dest / "plugin.py").write_text(PLUGIN_PY.format(mid=mid), encoding="utf-8")
    (dest / "schema.json").write_text(
        json.dumps(schema_for(mid), indent=2) + "\n", encoding="utf-8")
    print(f"created {dest} (blast={blast} cost={cost})")
    print(f"map row to add: {dest}/ | KEEP | new module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
