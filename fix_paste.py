#!/usr/bin/env python3
"""fix_paste.py - repair wrap-damaged lines in pegasus_finish.py.

Splits long single-line expressions into short statements so a wrapped paste
cannot break them. Verifies the file compiles afterwards.

    python fix_paste.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "pegasus_finish.py"

# marker in the damaged/risky line -> replacement body (indent is preserved)
FIXES = [
    ("ok(str(data", [
        'q9 = data["q9"]',
        'total = data["total"]',
        'ok(str(q9) + " q9 paths, " + str(total) + " routes total")',
    ]),
    ('die("npm ci failed: "', [
        'tail = ((p.stderr or p.stdout).strip().splitlines() or ["?"])[-1][:200]',
        'die("npm ci failed: " + tail)',
    ]),
    ('warn("desktop install: "', [
        'tail = ((p.stderr or p.stdout).strip().splitlines() or ["?"])[-1][:160]',
        'warn("desktop install: " + tail)',
    ]),
    ('ok("route_probe clean: "', [
        'head = (p.stdout or "").strip()[:110]',
        'ok("route_probe clean: " + head)',
    ]),
    ("msg = prefix +", [
        'msg = prefix + " release " + VERSION',
        'msg += " - register Q9, fix scripts, rewrite README\\n\\n" + body',
    ]),
]


def main() -> int:
    if not TARGET.exists():
        print("pegasus_finish.py not found next to this script")
        return 1
    lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)

    out: list[str] = []
    i = 0
    changed = 0
    while i < len(lines):
        line = lines[i]
        hit = next((body for marker, body in FIXES if marker in line), None)
        if hit is None:
            out.append(line)
            i += 1
            continue

        indent = re.match(r"\s*", line).group(0)
        # swallow orphaned continuation of a wrap-broken statement
        if "ok(str(data" in line:
            j = i + 1
            while j < len(lines) and j < i + 6:
                if 'routes total")' in lines[j]:
                    j += 1
                    break
                if lines[j].lstrip().startswith(("if ", "# ", "p = ")):
                    break
                j += 1
            i = j
        else:
            i += 1

        for body in hit:
            out.append(indent + body + "\n")
        changed += 1

    TARGET.write_text("".join(out), encoding="utf-8", newline="\n")
    print(f"rewrote {changed} statement(s)")

    p = subprocess.run([sys.executable, "-m", "py_compile", str(TARGET)],
                       capture_output=True, text=True)
    if p.returncode == 0:
        print("compiles clean")
        return 0
    print(p.stderr[-1500:])
    print("\nif a region is still broken, hand-edit it to the shape shown in")
    print("the FIXES table above - short statements, one per line.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())