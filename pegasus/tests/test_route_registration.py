"""Every route a module declares must reach the live url_map.

Four modules were once written and never registered; the console called their
paths and got 404s. The earlier version of this test matched "<mod>.register("
as a substring of app.py, which a comment satisfies and which passes vacuously
if the glob returns nothing. This one extracts the literal paths each module
declares and asserts they are routable, with floors so it cannot go quiet.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "ui" / "web" / "backend"
DECORATOR = re.compile(r'@app\.(?:get|post|put|patch|delete|route)\(\s*["\']([^"\']+)["\']')

# app.py owns the factory, __init__.py is a package marker
EXEMPT = {"__init__.py", "app.py"}

# floor: below this the scan is not really scanning
MIN_MODULES = 20
MIN_PATHS = 150


def declared_paths() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in BACKEND.glob("*_routes.py"):
        if path.name in EXEMPT:
            continue
        hits = DECORATOR.findall(path.read_text(encoding="utf-8"))
        if hits:
            out[path.name] = hits
    return out


@pytest.fixture(scope="module")
def url_map() -> set[str]:
    from pegasus.ui.web.backend.app import create_app
    return {r.rule for r in create_app().url_map.iter_rules()}


def test_scan_is_not_vacuous():
    declared = declared_paths()
    assert len(declared) >= MIN_MODULES, (
        f"only {len(declared)} route module(s) found under {BACKEND}")
    total = sum(len(v) for v in declared.values())
    assert total >= MIN_PATHS, f"only {total} literal route path(s) found"


def test_every_declared_path_is_routable(url_map: set[str]):
    missing: dict[str, list[str]] = {}
    for module, paths in declared_paths().items():
        gone = [p for p in paths if p not in url_map]
        if gone:
            missing[module] = gone
    assert not missing, (
        "route module(s) declare paths the app never registers - add the "
        f"register() call in create_app(): {missing}")
