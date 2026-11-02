#!/usr/bin/env python3
"""Diff capability names declared in registries against those in README."""
import re, sys
from pathlib import Path

REGISTRIES = ("pegasus/core/plugin/modules/base.py", "pegasus/modules/base.py",
              "weapons/registry.py", "exploits/registry.py", "c2/registry.py",
              "rat/commands.py")
README, OUT = Path("README.md"), Path("build/parity.diff")
REG_RE = re.compile(r"""register\(\s*["']([a-z][a-z0-9_]*)["']""")
CAP_RE = re.compile(r"(?m)^CAPABILITIES\s*[:=].*$")
NAME_RE = re.compile(r"""["']([a-z][a-z0-9_]{2,})["']""")
DOC_RE = re.compile(r"`([a-z][a-z0-9_]{2,})`")


def declared() -> set[str]:
    names: set[str] = set()
    for rel in REGISTRIES:
        p = Path(rel)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        names |= set(REG_RE.findall(text))
        for line in CAP_RE.findall(text):
            names |= set(NAME_RE.findall(line))
    return names


def main() -> int:
    found = [r for r in REGISTRIES if Path(r).exists()]
    if not found:
        sys.exit("PRECONDITION: no registry file found")
    if not README.exists():
        sys.exit("PRECONDITION: README.md missing")
    names = declared()
    if not names:
        sys.exit("PRECONDITION: no capability names parsed")
    documented = set(DOC_RE.findall(README.read_text(encoding="utf-8", errors="replace")))
    undoc, orphan = sorted(names - documented), sorted(documented - names)
    lines = ["# registry vs README", "", "registries: " + ", ".join(found), "",
             "## declared, not documented"]
    lines += [f"- {n}" for n in undoc] or ["- none"]
    lines += ["", "## documented, not declared (informational)"]
    lines += [f"- {n}" for n in orphan[:200]] or ["- none"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(names)} declared, {len(undoc)} undocumented")
    if undoc:
        return 2
    print("parity clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
