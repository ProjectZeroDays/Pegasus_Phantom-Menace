#!/usr/bin/env python3
"""Lint module manifests: ids, caps, tiers, deps, cycles, orphans.

Plan sections 115-116. Every cap comparison goes through scripts/capreg.py, the
same module caps_matrix uses, so the two lints cannot disagree about what a cap
is or whether a transport provides it. An orphan cap fails here as well as
there — a green modules_lint with a red matrix is not reachable.

Exit 3 on a malformed tree, 2 on any violation.
"""
import re, sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capreg

MANIFESTS = Path("post_exploitation/manifests")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,23}$")
REQUIRED = {"id", "title", "category", "tier"}


def load():
    if not MANIFESTS.exists():
        return None, []
    specs, errs = {}, []
    for f in sorted(MANIFESTS.glob("*.yaml")):
        raw = yaml.safe_load(f.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            errs.append(f"{f.name}: not a list")
            continue
        for e in raw:
            if not isinstance(e, dict):
                errs.append(f"{f.name}: entry is not a mapping")
                continue
            e["_file"] = f.name
            specs[e.get("id", "?")] = e
    return specs, errs


def main() -> int:
    try:
        known = set(capreg.cap_values())
        provided = capreg.providers()
    except capreg.Precondition as exc:
        sys.exit(f"PRECONDITION: {exc}")
    allowed = capreg.allowlist()

    specs, errs = load()
    if specs is None:
        sys.exit(f"PRECONDITION: {MANIFESTS} missing")

    for phantom in capreg.phantom_provides(known, provided):
        errs.append(f"transports/registry.yaml: phantom cap {phantom} "
                    f"(not in {capreg.CAPS})")

    waived = set()
    for sid, s in specs.items():
        where = f"{s['_file']}:{sid}"
        missing = REQUIRED - set(s)
        if missing:
            errs.append(f"{where}: missing {sorted(missing)}")
        if not ID_RE.match(sid):
            errs.append(f"{where}: bad id")
        if s.get("tier") not in (1, 2, 3):
            errs.append(f"{where}: tier must be 1, 2 or 3")
        req = s.get("requires_caps") or {}
        if not isinstance(req, dict):
            errs.append(f"{where}: requires_caps must be a mapping")
            continue
        if not req.get("all") and not req.get("any"):
            errs.append(f"{where}: needs requires_caps.all or .any")
        for field in ("all", "any", "optional"):
            for c in req.get(field) or []:
                if c not in known:
                    errs.append(f"{where}: unknown cap {c}")
                elif c not in provided:
                    if c in allowed:
                        waived.add(c)
                    else:
                        errs.append(f"{where}: orphan cap {c} "
                                    f"(no transport provides it)")
        for dep in s.get("depends_on") or []:
            if dep not in specs:
                errs.append(f"{where}: unresolved dep {dep}")

    # a cap no manifest references is still a cap with no transport
    reported = {e.split("orphan cap ", 1)[1].split(" ", 1)[0]
                for e in errs if "orphan cap " in e}
    for c in sorted(known - provided.keys() - allowed.keys()):
        if c not in reported:
            errs.append(f"cap enum: orphan cap {c} (no transport provides it)")

    graph = {k: list(v.get("depends_on") or []) for k, v in specs.items()}
    state: dict[str, int] = {}

    def visit(n: str, trail: list[str]) -> None:
        if state.get(n) == 1:
            errs.append("cycle: " + " -> ".join(trail + [n]))
            return
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in graph.get(n, []):
            visit(d, trail + [n])
        state[n] = 2

    for n in graph:
        visit(n, [])

    if errs:
        print("\n".join(errs))
        print(f"\n{len(errs)} violation(s) across {len(specs)} manifest(s)")
        if waived:
            print(f"waived orphans: {', '.join(sorted(waived))}")
        return 2
    tiers = {t: sum(1 for s in specs.values() if s.get("tier") == t) for t in (1, 2, 3)}
    print(f"{len(specs)} manifests valid (T1={tiers[1]} T2={tiers[2]} T3={tiers[3]})")
    if waived:
        print(f"waived orphans: {', '.join(sorted(waived))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
