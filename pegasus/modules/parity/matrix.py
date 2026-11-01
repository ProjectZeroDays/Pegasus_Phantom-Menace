"""Parity, derived from code. Numbers move when code moves."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _count_vectors() -> int:
    from ..delivery import adapters, legacy
    return len(adapters.REGISTRY) + len(legacy.LEGACY)


def _count_postex() -> int:
    src = (ROOT / "modules" / "autonomous" / "engine.py").read_text(encoding="utf-8")
    return len(re.findall(r'^\s*\("(\w+)", self\._', src, re.M))


def _count_pages() -> int:
    return len(list((ROOT / "ui" / "web" / "src" / "pages").glob("*.tsx")))


DOMAINS = {
    "delivery": (_count_vectors, 13, "carrier channels; no baseband/SS7"),
    "post-exploit": (_count_postex, 9, "chain steps; wallet/browser best-effort"),
    "ui": (_count_pages, 8, "pages present"),
}


def report() -> dict:
    out = {}
    for name, (fn, target, note) in DOMAINS.items():
        done = fn()
        out[name] = {"target": target, "done": done,
                     "pct": round(min(done / target, 1.0) * 100), "note": note}
    total = sum(d["target"] for d in out.values())
    done = sum(d["done"] for d in out.values())
    return {"domains": out, "overall_pct": round(min(done / total, 1.0) * 100, 1)}
