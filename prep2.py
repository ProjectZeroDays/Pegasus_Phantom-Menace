#!/usr/bin/env python3
"""prep2.py - find the real hook, report route duplication, run the electron stage."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "pegasus_finish.py"
E = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def sh(*cmd, cwd=ROOT, timeout=1800):
    p = subprocess.run(cmd, cwd=cwd, env=E, capture_output=True, text=True,
                       errors="replace", timeout=timeout)
    return p


print("== 1. where is the hook ==")
hp = sh("git", "config", "--get", "core.hooksPath").stdout.strip()
print(f"  core.hooksPath = {hp or '(unset)'}")

candidates: list[Path] = []
if hp:
    base = (ROOT / hp) if not os.path.isabs(hp) else Path(hp)
    if base.is_dir():
        candidates += [p for p in base.iterdir() if p.is_file()]
hooks_dir = ROOT / ".git" / "hooks"
if hooks_dir.is_dir():
    candidates += [p for p in hooks_dir.iterdir()
                   if p.is_file() and not p.name.endswith(".sample")]

print(f"  {len(candidates)} live hook file(s):")
for p in candidates:
    print(f"    {p.relative_to(ROOT)}")

rule_hook = None
for p in candidates:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    if "prefix" not in text.lower():
        continue
    rule_hook = p
    print(f"\n  --- prefix rule in {p.relative_to(ROOT)} ---")
    for i, line in enumerate(text.splitlines(), 1):
        if "prefix" in line.lower() or "P1" in line or "grep" in line.lower():
            print(f"  {i:4}| {line.strip()[:150]}")
    print("  --- end ---")

if rule_hook is None:
    print("\n  no hook file mentions 'prefix' - printing the first live hook whole")
    if candidates:
        for i, line in enumerate(
                candidates[0].read_text(encoding="utf-8", errors="replace").splitlines()[:40], 1):
            print(f"  {i:4}| {line[:150]}")

print("\n== 2. patch pegasus_finish.py to find the hook ==")
if not TARGET.exists():
    print("  pegasus_finish.py missing")
else:
    src = TARGET.read_text(encoding="utf-8")
    if "def hook_path" in src:
        print("  already patched")
    else:
        resolver = '''
def hook_path():
    """The real hook: core.hooksPath, else .git/hooks, else .githooks."""
    import subprocess as _sp
    try:
        hp = _sp.run(["git", "config", "--get", "core.hooksPath"], cwd=ROOT,
                     capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        hp = ""
    dirs = []
    if hp:
        dirs.append(Path(hp) if os.path.isabs(hp) else ROOT / hp)
    dirs.append(ROOT / ".git" / "hooks")
    dirs.append(ROOT / ".githooks")
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and not p.name.endswith(".sample"):
                return p
    return None

'''
        pairs = [
            ('HOOK = ROOT / ".githooks" / "require"',
             'HOOK = ROOT / ".githooks" / "require"  # fallback only; see hook_path()'),
            ("def derive_prefixes():", resolver.lstrip("\n") + "\ndef derive_prefixes():"),
            ('if not HOOK.exists():\n        warn("no hook")\n        return ["P16:"]',
             'hook = hook_path()\n    if hook is None:\n        warn("no hook found")\n        return ["P16:"]'),
            ('src = HOOK.read_text(encoding="utf-8", errors="replace")',
             'src = hook.read_text(encoding="utf-8", errors="replace")'),
            ('if HOOK.exists():\n        for i, line in enumerate(HOOK.read_text(encoding="utf-8", errors="replace").splitlines(), 1):',
             'hook = hook_path()\n    if hook is not None:\n        for i, line in enumerate(hook.read_text(encoding="utf-8", errors="replace").splitlines(), 1):'),
        ]
        ok = True
        for old, new in pairs:
            if old not in src:
                print(f"  MISS anchor: {old.splitlines()[0][:70]}")
                ok = False
                continue
            src = src.replace(old, new, 1)
        if ok:
            TARGET.write_text(src, encoding="utf-8", newline="\n")
            r = sh(sys.executable, "-m", "py_compile", str(TARGET))
            print("  patched, compiles" if r.returncode == 0 else "  patched but BROKEN:\n" + r.stderr[-500:])
        else:
            print("  not patched - one or more anchors moved")

print("\n== 3. route duplication ==")
r = sh(sys.executable, "scripts/route_probe.py", timeout=600)
print("  exit " + str(r.returncode))
for line in ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-12:]:
    print("  " + line[:200])

code = ("from pegasus.ui.web.backend.app import create_app;"
        "import collections;"
        "rules=[(x.rule, ','.join(sorted(x.methods-{'HEAD','OPTIONS'}))) for x in create_app().url_map.iter_rules()];"
        "d=collections.Counter(rules);"
        "print('dups', [k for k,v in d.items() if v>1][:10]);"
        "print('total', len(rules))")
r = sh(sys.executable, "-c", code, timeout=300)
print("  " + (r.stdout or r.stderr).strip().replace("\n", "\n  ")[:800])

print("\n== 4. electron stage ==")
r = sh(sys.executable, "pegasus_finish.py", "--yes", "--only", "electron", timeout=3600)
tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
print("  exit " + str(r.returncode))
for line in tail[-25:]:
    print("  " + line[:200])