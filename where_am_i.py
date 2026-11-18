#!/usr/bin/env python3
"""where_am_i.py - read-only state probe. Changes nothing."""
from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
E = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def sh(*cmd, cwd=ROOT):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              errors="replace", timeout=120)
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


print("== syntax ==")
for name in ("pegasus_finish.py", "fix_paste.py", "scripts/route_probe.py",
             "pegasus/ui/web/backend/q9_routes.py",
             "pegasus/ui/web/backend/c2_routes.py",
             "pegasus/modules/c2/server.py", "start_server.py"):
    p = ROOT / name
    if not p.exists():
        print(f"  MISSING  {name}")
        continue
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"  ok       {name}")
    except py_compile.PyCompileError as exc:
        print(f"  BROKEN   {name}: {str(exc).splitlines()[0][:90]}")

print("\n== electron ==")
base = ROOT / "electron" / "node_modules" / "electron"
print(f"  dir        {base.exists()}")
print(f"  path.txt   {(base / 'path.txt').exists()}")
print(f"  electron.exe {(base / 'dist' / 'electron.exe').exists()}")
for key in os.environ:
    if key.upper().endswith("ELECTRON_SKIP_BINARY_DOWNLOAD"):
        print(f"  skip var   {key}={os.environ[key]}")
r = sh("node", "-e", "console.log(require('electron'))", cwd=ROOT / "electron")
print(f"  require    {'ok' if r.returncode == 0 else 'THROWS'}")

print("\n== routes ==")
code = (
    "from pegasus.ui.web.backend.app import create_app;"
    "r=[x.rule for x in create_app().url_map.iter_rules()];"
    "print('q9', len([p for p in r if p.startswith('/api/q9/')]), 'total', len(r))"
)
r = sh(sys.executable, "-c", code)
print("  " + (r.stdout or r.stderr).strip().splitlines()[-1][:120] if (r.stdout or r.stderr) else "  no output")

print("\n== versions ==")
for rel in ("pegasus/VERSION", "electron/package.json",
            "pegasus/ui/web/package.json", "packages/pegasus-desktop/package.json"):
    p = ROOT / rel
    if not p.exists():
        print(f"  MISSING {rel}")
        continue
    if rel.endswith("VERSION"):
        print(f"  {rel} = {p.read_text(encoding='utf-8').strip()}")
    else:
        try:
            print(f"  {rel} = {json.loads(p.read_text(encoding='utf-8')).get('version')}")
        except Exception:
            print(f"  {rel} unreadable")

print("\n== readme ==")
rd = ROOT / "README.md"
if rd.exists():
    for line in rd.read_text(encoding="utf-8").splitlines()[:8]:
        if "Version" in line or "Status" in line:
            print("  " + line.strip()[:100])

print("\n== git ==")
print("  branch  " + sh("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip())
print("  head    " + sh("git", "rev-parse", "--short", "HEAD").stdout.strip())
dirty = sh("git", "status", "--porcelain").stdout.strip().splitlines()
print(f"  dirty   {len(dirty)} path(s)")
print("  ahead   " + sh("git", "rev-list", "--count", "@{u}..HEAD").stdout.strip())

print("\n== hook ==")
hook = ROOT / ".githooks" / "require"
print(f"  exists  {hook.exists()}")
if hook.exists():
    for i, line in enumerate(hook.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if "prefix" in line.lower() or "P1" in line:
            print(f"  {i}| {line.strip()[:110]}")

print("\n== desktop logs ==")
desk = Path(os.environ.get("PEGASUS_LOG_DIR", r"C:\Users\Project Zero\Desktop"))
if desk.is_dir():
    logs = sorted(desk.glob("*.txt.log"))[-5:]
    print(f"  {len(list(desk.glob('*.txt.log')))} log(s), newest:")
    for p in logs:
        print(f"    {p.name}  {p.stat().st_size} B")
else:
    print("  desktop path not found")