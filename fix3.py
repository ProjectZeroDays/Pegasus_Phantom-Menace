#!/usr/bin/env python3
"""Cast the dashboard counts bag at its read site."""
from __future__ import annotations

import subprocess
from pathlib import Path

WEB = Path("pegasus/ui/web")
PAGE = WEB / "src" / "pages" / "MissionControl.tsx"
OLD = "  const counts = summary.data?.summary.counts ?? {};"
NEW = "  const counts = (summary.data?.summary.counts ?? {}) as Record<string, any>;"


def main() -> int:
    if not (WEB / "src" / "pages").is_dir():
        print("run from the repo root"); return 1

    text = PAGE.read_text(encoding="utf-8")
    if NEW in text:
        print("  skip  already cast")
    elif OLD in text:
        PAGE.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
        print("  ok    counts cast")
    else:
        print("  FAIL  anchor not found")
        for line in text.split("\n"):
            if "counts" in line and "summary" in line:
                print(f"    {line!r}")
        return 2

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