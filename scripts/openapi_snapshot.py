#!/usr/bin/env python3
"""Freeze the Flask URL map before dashboard_server.py is split into blueprints."""
import hashlib, json, sys
from pathlib import Path

SPEC = Path("docs/api/openapi.yaml")
ROUTES = Path("build/openapi.routes.json")
SHA = Path("build/openapi.sha256")

CANDIDATES = (
    ("pegasus.ui.web.server", "app"), ("pegasus.ui.web.server", "create_app"),
    ("pegasus.ui.api.app", "app"), ("pegasus.ui.api.app", "create_app"),
    ("dashboard_server", "app"),
)


def load_app():
    last = "no candidate module imported"
    for mod, attr in CANDIDATES:
        try:
            m = __import__(mod, fromlist=[attr])
        except Exception as exc:
            last = f"{mod}: {exc}"
            continue
        obj = getattr(m, attr, None)
        if obj is None:
            last = f"{mod}.{attr} missing"
            continue
        try:
            return obj() if attr == "create_app" else obj
        except Exception as exc:
            last = f"{mod}.{attr}() raised {exc}"
    sys.exit(f"PRECONDITION: cannot import app — {last}")


def collect(app):
    out = []
    for rule in app.url_map.iter_rules():
        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
        if not methods:
            continue
        out.append({"rule": str(rule), "methods": methods,
                    "endpoint": rule.endpoint, "args": sorted(rule.arguments)})
    out.sort(key=lambda r: (r["rule"], r["methods"]))
    return out


def main() -> int:
    routes = collect(load_app())
    if not routes:
        sys.exit("PRECONDITION: url_map is empty")
    ROUTES.parent.mkdir(parents=True, exist_ok=True)
    ROUTES.write_text(json.dumps(routes, indent=2) + "\n", encoding="utf-8")
    lines = ["openapi: 3.0.3", "info:", "  title: Pegasus", "  version: snapshot", "paths:"]
    for r in routes:
        lines.append(f"  {r['rule']}:")
        for m in r["methods"]:
            lines += [f"    {m.lower()}:", f"      operationId: {r['endpoint']}",
                      "      responses:", "        '200': {description: ok}"]
    SPEC.parent.mkdir(parents=True, exist_ok=True)
    SPEC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = hashlib.sha256()
    for p in (SPEC, ROUTES):
        digest.update(p.read_bytes())
    SHA.write_text(digest.hexdigest() + "  openapi\n", encoding="utf-8")
    print(f"{len(routes)} routes frozen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
