#!/usr/bin/env python3
"""diag_main.py - find out why pegasus_finish.py runs silently."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
T = ROOT / "pegasus_finish.py"
E = {**os.environ, "PYTHONIOENCODING": "utf-8"}

if not T.exists():
    print("pegasus_finish.py MISSING")
    raise SystemExit(1)

src = T.read_text(encoding="utf-8")
lines = src.splitlines()
print(f"size {len(src)} B, {len(lines)} lines")
print(f"  def main            {'yes' if 'def main(' in src else 'NO'}")
print(f"  __main__ guard      {'yes' if '__name__' in src else 'NO'}")
print(f"  raise SystemExit    {'yes' if 'SystemExit' in src else 'NO'}")
print(f"  STAGES list         {'yes' if 'STAGES = [' in src else 'NO'}")
print(f"  stage_electron      {'yes' if 'def stage_electron(' in src else 'NO'}")
print(f"  say( calls          {src.count('say(')}")
print(f"  def count           {len(re.findall(r'^def ', src, re.M))}")

print("\n--- last 12 lines ---")
for i, line in enumerate(lines[-12:], len(lines) - 11):
    print(f"{i:4}| {line[:120]}")

print("\n--- import test ---")
r = subprocess.run([sys.executable, "-c",
                    "import pegasus_finish as m;"
                    "print('has main:', hasattr(m, 'main'));"
                    "print('has stage_electron:', hasattr(m, 'stage_electron'))"],
                   cwd=ROOT, capture_output=True, text=True, env=E)
print("  " + ((r.stdout or "") + (r.stderr or "")).strip().replace("\n", "\n  ")[:600])

if "def main(" in src and "__name__" not in src:
    print("\n--- main() exists but is never invoked: appending the guard ---")
    T.write_text(src.rstrip("\n") + "\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n",
                 encoding="utf-8", newline="\n")
    r = subprocess.run([sys.executable, "-m", "py_compile", str(T)],
                       capture_output=True, text=True, env=E)
    print("  compiles" if r.returncode == 0 else "  BROKEN:\n" + r.stderr[-400:])
elif "def main(" not in src:
    print("\n--- main() is GONE - the tail of the file was lost ---")
else:
    print("\n--- guard present; the silence is elsewhere ---")