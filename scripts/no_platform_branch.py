#!/usr/bin/env python3
"""Fail if a module body branches on platform instead of capabilities.

Plan section 113. platform_hint is grouping only; the gate is requires_caps.
Exit 3 if no module file exists, 2 on any branch found.
"""
import re, sys
from pathlib import Path

ROOT = Path("pegasus/modules")
PATTERNS = [
    (re.compile(r"\bif\s+[\w.]*platform\s*[=!]="), "platform equality"),
    (re.compile(r"\bis_android\b|\bis_ios\b|\bis_windows\b"), "is_<os> helper"),
    (re.compile(r"\bos\.name\s*[=!]="), "os.name comparison"),
    (re.compile(r"\bsys\.platform\b"), "sys.platform"),
]
ALLOW = Path("build/noplatform.allow")


def main() -> int:
    files = sorted(ROOT.rglob("module.py")) if ROOT.exists() else []
    if not files:
        sys.exit(f"PRECONDITION: no module.py under {ROOT}")
    allow = set()
    if ALLOW.exists():
        allow = {ln.split("#")[0].strip() for ln in ALLOW.read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")}
    hits = []
    for f in files:
        rel = f.as_posix()
        if rel in allow:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.split("#")[0]
            for pat, label in PATTERNS:
                if pat.search(code):
                    hits.append(f"{rel}:{i}: {label}: {code.strip()[:70]}")
                    break
    if hits:
        print("\n".join(hits))
        print(f"\n{len(hits)} platform branch(es) across {len(files)} module(s)")
        print("move the decision into requires_caps, or add the file to build/noplatform.allow")
        return 2
    print(f"no platform branches in {len(files)} module(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
