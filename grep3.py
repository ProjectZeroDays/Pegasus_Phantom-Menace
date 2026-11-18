#!/usr/bin/env python3
"""prep3.py - fix the hook regex, fix the bootstrap placement, verify both."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOOK = ROOT / ".githooks" / "commit-msg"
PROBE = ROOT / "scripts" / "route_probe.py"
E = {**os.environ, "PYTHONIOENCODING": "utf-8"}

print("== 1. hook regex ==")
if not HOOK.exists():
    print("  commit-msg missing")
else:
    text = HOOK.read_text(encoding="utf-8")
    if "P[0-9]+[a-c]?" in text:
        print("  already accepts multi-digit")
    else:
        new = text.replace("P[0-9][a-c]?", "P[0-9]+[a-c]?")
        if new == text:
            print("  pattern not found - printing the file")
            for i, line in enumerate(text.splitlines(), 1):
                print(f"  {i:4}| {line}")
        else:
            HOOK.write_text(new, encoding="utf-8", newline="\n")
            print("  P[0-9][a-c]? -> P[0-9]+[a-c]?  (its own example now matches)")

    # prove it against the real subjects we need
    m = re.search(r"grep -Eq '([^']+)'", HOOK.read_text(encoding="utf-8"))
    if m:
        pat = re.compile(m.group(1))
        print("  rule: " + m.group(1))
        for subject in ("P16: release 2.3.4", "P11: add browser_creds",
                        "P9: x", "PLAN: x", "P12a: x", "P16 bad", "nope"):
            print(f"    {'PASS' if pat.match(subject) else 'fail'}  {subject}")

print("\n== 2. route_probe bootstrap ==")
if not PROBE.exists():
    print("  missing")
else:
    text = PROBE.read_text(encoding="utf-8")
    boot = (
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "_ROOT = Path(__file__).resolve().parents[1]\n"
        "if str(_ROOT) not in sys.path:\n"
        "    sys.path.insert(0, str(_ROOT))\n"
    )
    # strip any existing (misplaced) bootstrap
    text = re.sub(r"import sys\nfrom pathlib import Path\n\n_ROOT = .*?\n(?:.*?\n)*?    sys\.path\.insert\(0, str\(_ROOT\)\)\n", "", text, count=1)
    if "_ROOT = Path(__file__).resolve().parents[1]" in text:
        print("  still present after strip - leaving as-is")
    else:
        anchor = re.search(r"^(from pegasus|import pegasus)", text, re.M)
        if not anchor:
            print("  no pegasus import found")
        else:
            text = text[:anchor.start()] + boot + "\n" + text[anchor.start():]
            PROBE.write_text(text, encoding="utf-8", newline="\n")
            print("  bootstrap inserted before the pegasus import")

    r = subprocess.run([sys.executable, "-m", "py_compile", str(PROBE)],
                       capture_output=True, text=True, env=E)
    print("  compiles" if r.returncode == 0 else "  BROKEN:\n" + r.stderr[-400:])
    r = subprocess.run([sys.executable, "scripts/route_probe.py"],
                       capture_output=True, text=True, env=E, timeout=600)
    print("  route_probe exit " + str(r.returncode))
    for line in ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-6:]:
        print("  " + line[:160])