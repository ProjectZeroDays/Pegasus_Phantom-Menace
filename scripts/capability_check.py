#!/usr/bin/env python3
"""Dashboard is renamed Capability. Exit 3 if the web tree is absent, 2 on drift."""
import sys
from pathlib import Path

WEB = Path("pegasus/ui/web/src")
OLD, NEW = "Dashboard", "Capability"
SKIP = {"node_modules", "dist", ".vite"}


def files():
    if not WEB.exists():
        return []
    return [p for p in WEB.rglob("*")
            if p.suffix in {".tsx", ".ts", ".jsx", ".js"}
            and not SKIP & set(p.parts)]


def main() -> int:
    fs = files()
    if not fs:
        sys.exit(f"PRECONDITION: no source under {WEB}")
    stale, renamed = [], []
    for p in fs:
        text = p.read_text(encoding="utf-8", errors="replace")
        if OLD in text:
            stale.append(p.as_posix())
        if NEW in text:
            renamed.append(p.as_posix())
    if stale:
        print(f"{len(stale)} file(s) still say {OLD}:")
        for s in stale:
            print(f"  {s}")
        print(f"rename to {NEW} before P6")
        return 2
    if not renamed:
        print(f"{NEW} label not found anywhere")
        return 2
    print(f"{NEW} label present, {OLD} gone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
