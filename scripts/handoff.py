#!/usr/bin/env python3
"""Extract the handoff section of docs/PLAN.md into docs/HANDOFF.md."""
import os, re, sys
from pathlib import Path

PLAN = Path("docs/PLAN.md")
OUT = Path("docs/HANDOFF.md")
HEAD = re.compile(r"^## " + os.environ.get("HANDOFF_SECTION", r"60\."), re.M)


def extract() -> str:
    text = PLAN.read_text(encoding="utf-8")
    m = HEAD.search(text)
    if not m:
        sys.exit("PRECONDITION: handoff section not found in docs/PLAN.md")
    body = text[m.start():].rstrip() + "\n"
    if len(body) < 200:
        sys.exit("PRECONDITION: handoff section suspiciously short")
    return body


def main() -> int:
    body = extract()
    if "--check" in sys.argv:
        if not OUT.exists():
            print("PRECONDITION: docs/HANDOFF.md missing", file=sys.stderr)
            return 3
        if OUT.read_text(encoding="utf-8") != body:
            print("PRECONDITION: HANDOFF drifted from PLAN", file=sys.stderr)
            return 3
        print("handoff in sync")
        return 0
    OUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUT} ({len(body)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
