#!/usr/bin/env python3
"""Boot create_app, assert it serves and that no route is registered twice."""
from __future__ import annotations

import json
import sys

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pegasus.ui.web.backend.app import create_app


def main() -> int:
    app = create_app()
    rules = [(r.rule, ",".join(sorted(r.methods - {"HEAD", "OPTIONS"})))
             for r in app.url_map.iter_rules()]
    dupes = sorted({k for k in rules if rules.count(k) > 1})
    client = app.test_client()
    health = client.get("/api/health")
    print(json.dumps({"routes": len(rules), "duplicates": dupes,
                      "health": health.status_code}))
    if health.status_code != 200:
        print("health probe failed", file=sys.stderr)
        return 1
    if dupes:
        print(f"{len(dupes)} duplicate route(s): {dupes[:6]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
