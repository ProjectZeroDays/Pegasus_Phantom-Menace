#!/usr/bin/env python3
"""Narrow the last 30 type errors."""
from __future__ import annotations

import subprocess
from pathlib import Path

WEB = Path("pegasus/ui/web")
TYPES = WEB / "src" / "lib" / "types.ts"

EDITS = [
    ("run target objects", "targets?: string[];", "targets?: RunTarget[];"),
    ("notes object only", "notes?: DeviceNotes | string | null;", "notes?: DeviceNotes | null;"),
    ("component name", 'export interface ComponentStatus {\n  key?: string;', 'export interface ComponentStatus {\n  key?: string;\n  name?: string;'),
    ("counts absorbable", "summary?: { counts?: Record<string, number> };", "summary?: { counts?: any };"),
    ("plugin commands", "commands?: number[];", "commands?: PluginCommand[];"),
    ("plugin components", "components?: number[];", "components?: PluginComponent[];"),
]

NEW_INTERFACES = '''
export interface RunTarget {
  serial: string;
  transport?: string;
  score?: number;
  vector?: string;
  [key: string]: unknown;
}

export interface PluginCommand {
  name?: string;
  description?: string;
  [key: string]: unknown;
}

export interface PluginComponent {
  name?: string;
  title?: string;
  path?: string;
  [key: string]: unknown;
}
'''


def main() -> int:
    if not (WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    text = TYPES.read_text(encoding="utf-8")
    for name, old, new in EDITS:
        if old not in text:
            print(f"  FAIL {name}: {old[:60]!r}")
            return 2
        text = text.replace(old, new, 1)
        print(f"  ok   {name}")

    anchor = "\nexport interface Run {"
    if anchor not in text:
        print("  FAIL Run interface missing"); return 2
    text = text.replace(anchor, NEW_INTERFACES + anchor, 1)
    print("  ok   new interfaces")

    TYPES.write_text(text, encoding="utf-8")

    print("\ntypecheck")
    if subprocess.call("npx tsc --noEmit", cwd=str(WEB), shell=True) != 0:
        print("\nstill failing — not committing")
        return 3
    print("  clean")

    subprocess.call("git add -A", cwd=str(Path.cwd()), shell=True)
    subprocess.call(
        'git commit -m "web: restore src/lib, add supplementary device routes, fix series" '
        '-m "Types derived from page usage. Sweeps 5.1 5.3 7.1 7.2 8.1 8.2 8.3 10.1 12.3."',
        cwd=str(Path.cwd()), shell=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())