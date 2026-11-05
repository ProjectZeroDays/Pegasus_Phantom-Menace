#!/usr/bin/env python3
"""Report what app.py already defines, so the route blueprint can be trimmed."""
from __future__ import annotations

import re
from pathlib import Path

APP = Path("pegasus/ui/web/backend/app.py")
ROUTES = Path("pegasus/ui/web/backend/device_routes.py")

text = APP.read_text(encoding="utf-8")
lines = text.split("\n")

print(f"app.py: {len(lines)} lines\n")

print("-- secret handling --")
for n, line in enumerate(lines, 1):
    if re.search(r"secret", line, re.I):
        print(f"{n:4} {line}")

print("\n-- Flask construction / config --")
for n, line in enumerate(lines, 1):
    if re.search(r"Flask\(|app\.config|create_app|def register|\.register\(", line):
        print(f"{n:4} {line}")

print("\n-- declared routes --")
declared = set()
for n, line in enumerate(lines, 1):
    m = re.search(r'@app\.(get|post|put|patch|delete)\(\s*"([^"]+)"', line)
    if m:
        declared.add((m.group(1).upper(), m.group(2)))
        print(f"{n:4} {m.group(1).upper():6} {m.group(2)}")
print(f"\ntotal declared: {len(declared)}")

print("\n-- endpoint function names (collision risk) --")
names = set()
for line in lines:
    m = re.match(r"\s*def (\w+)\(", line)
    if m:
        names.add(m.group(1))

mine = ROUTES.read_text(encoding="utf-8") if ROUTES.exists() else ""
my_names = set(re.findall(r"^\s*def (\w+)\(", mine, re.M))
my_routes = set()
for line in mine.split("\n"):
    m = re.search(r'@app\.(get|post|put|patch|delete)\(\s*"([^"]+)"', line)
    if m:
        my_routes.add((m.group(1).upper(), m.group(2)))

clash_names = sorted(names & my_names)
print(f"shared function names: {clash_names or 'none'}")
print(f"device_routes routes already in app.py: {sorted(my_routes & declared) or 'none'}")
print(f"device_routes routes genuinely missing:  {sorted(my_routes - declared) or 'none'}")