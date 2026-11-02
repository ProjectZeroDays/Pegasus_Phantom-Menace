#!/usr/bin/env python3
"""Assert one version everywhere. Exit 1 on drift, 3 on a missing source."""
import json, re, sys
from pathlib import Path

VERSION = Path("pegasus/VERSION")
PYPROJECTS = (Path("pyproject.toml"), Path("pegasus/pyproject.toml"))
PACKAGE = Path("pegasus/ui/web/package.json")
RESOURCES = (Path("packaging/pyinstaller/version.txt"),
             Path("packaging/pyinstaller/version-web.txt"))
NUMS = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*\)")
STRV = re.compile(r"StringStruct\('(?:FileVersion|ProductVersion)',\s*'([0-9][0-9.]*)'\)")


def main() -> int:
    if not VERSION.exists():
        sys.exit("PRECONDITION: pegasus/VERSION missing")
    want = VERSION.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", want):
        sys.exit(f"PRECONDITION: bad version {want!r}")
    bad = 0
    for p in PYPROJECTS:
        if not p.exists():
            continue
        m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"))
        if not m:
            print(f"  warn {p}: no version field")
        elif m.group(1) != want:
            print(f"  FAIL {p}: {m.group(1)} != {want}")
            bad = 1
        else:
            print(f"  ok   {p}")
    if PACKAGE.exists():
        got = json.loads(PACKAGE.read_text(encoding="utf-8")).get("version")
        if got != want:
            print(f"  FAIL {PACKAGE}: {got} != {want}")
            bad = 1
        else:
            print(f"  ok   {PACKAGE}")
    for p in RESOURCES:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        seen = {".".join(n) for n in NUMS.findall(text)} | set(STRV.findall(text))
        if seen != {want}:
            print(f"  FAIL {p}: {sorted(seen)} != {want}")
            bad = 1
        else:
            print(f"  ok   {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
