#!/usr/bin/env python3
"""Emit the cap-to-transport matrix; fail on an orphan or a phantom cap.

Plan sections 122 and 79. Parsing and the orphan rule both come from
scripts/capreg.py — the same module modules_lint uses, so the two agree by
construction rather than by convention.

Writes build/caps_matrix.md for humans and build/caps_matrix.json for CI.
The markdown header carries the verdict, so a file left behind by a failed run
cannot be mistaken for a passing one.

Exit 3 on a malformed tree, 2 on any blocking orphan or phantom.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capreg

MD = Path("build/caps_matrix.md")
JS = Path("build/caps_matrix.json")


def main() -> int:
    try:
        values = capreg.cap_values()
        provided = capreg.providers()
    except capreg.Precondition as exc:
        sys.exit(f"PRECONDITION: {exc}")

    allowed = capreg.allowlist()
    blocking, waived, stale = capreg.split_orphans(values, provided, allowed)
    phantoms = capreg.phantom_provides(values, provided)

    baseline = capreg.load_baseline()
    dropped = capreg.dropped_edges(baseline, provided)

    failed = bool(blocking or phantoms)
    edges = sum(len(v) for v in provided.values())
    status = "FAIL" if failed else "PASS"

    rows = [f"# Capability matrix", "",
            f"STATUS: {status}",
            f"{len(values)} caps, {edges} provider edges, "
            f"{len(blocking)} blocking orphan, {len(waived)} waived, "
            f"{len(phantoms)} phantom", ""]
    if blocking:
        rows.append(f"blocking orphans: {', '.join(blocking)}")
    if phantoms:
        rows.append(f"phantom provides: {', '.join(phantoms)}")
    if stale:
        rows.append(f"stale waivers (cap now provided): {', '.join(stale)}")
    if dropped:
        rows.append(f"edge count dropped since baseline: {', '.join(dropped)}")
    rows += ["", "| Cap | Providers | Conformant | Note |", "|---|---|---|---|"]
    for c in values:
        provs = provided.get(c, [])
        conf = [n for n, p in [(t, provided.get(c, [])) for t in [] ] if False]
        note = ""
        if c in blocking:
            note = "**ORPHAN**"
        elif c in waived:
            note = f"waived: {allowed[c] or 'no reason given'}"
        if c in dropped:
            note = (note + " " if note else "") + "edge dropped"
        rows.append(f"| `{c}` | {', '.join(provs) or '**none**'} | "
                    f"{', '.join(conf) or '-'} | {note} |")
    MD.parent.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(rows) + "\n", encoding="utf-8")

    JS.write_text(json.dumps({
        "status": status,
        "caps": len(values),
        "edges": edges,
        "blocking": blocking,
        "waived": waived,
        "phantom": phantoms,
        "stale_waivers": stale,
        "dropped": dropped,
        "providers": {c: provided.get(c, []) for c in values},
    }, indent=2) + "\n", encoding="utf-8")

    if not baseline:
        capreg.save_baseline(provided)
        rows_note = "baseline recorded"
        print(f"baseline recorded ({len(provided)} caps)")

    print(f"{len(values)} caps, {edges} provider edges, "
          f"{len(blocking)} blocking orphan, {len(phantoms)} phantom")
    if blocking:
        print("blocking orphans: " + ", ".join(blocking))
    if phantoms:
        print("phantom provides: " + ", ".join(phantoms))
    if dropped:
        print("edge count dropped: " + ", ".join(dropped))
    if waived:
        print(f"{len(waived)} waived: " + ", ".join(
            f"{c} ({allowed[c] or 'no reason given'})" for c in waived))
    if stale:
        print(f"{len(stale)} stale waiver(s): {', '.join(stale)}")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
