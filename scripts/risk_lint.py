#!/usr/bin/env python3
"""Every risk needs a detector, a ladder, a proof, an owner and an SLA.

Plan section 118. No risk without a detector; no detector without a proof.
Exit 3 on a missing register, 2 on any incomplete record.
"""
import re, sys
from pathlib import Path
import yaml

REGISTER = Path("risk/register.yaml")
REQUIRED = {"id", "title", "area", "severity", "detector", "proof", "owner", "sla_hours"}
AREAS = {"device", "data", "truth", "crypto", "infra", "ops"}
SEVERITIES = {"critical", "high", "medium", "low"}
ID_RE = re.compile(r"^R-[A-Z]+-\d{2}$")


def main() -> int:
    if not REGISTER.exists():
        sys.exit(f"PRECONDITION: {REGISTER} missing")
    records = yaml.safe_load(REGISTER.read_text(encoding="utf-8")) or []
    if not isinstance(records, list) or not records:
        sys.exit("PRECONDITION: register is empty")
    errs, seen = [], set()
    for r in records:
        rid = r.get("id", "?")
        missing = REQUIRED - set(r)
        if missing:
            errs.append(f"{rid}: missing {sorted(missing)}")
        if not ID_RE.match(str(rid)):
            errs.append(f"{rid}: bad id shape")
        if rid in seen:
            errs.append(f"{rid}: duplicate")
        seen.add(rid)
        if r.get("area") not in AREAS:
            errs.append(f"{rid}: bad area")
        if r.get("severity") not in SEVERITIES:
            errs.append(f"{rid}: bad severity")
        if not r.get("ladder"):
            errs.append(f"{rid}: no ladder")
        if not r.get("auto"):
            errs.append(f"{rid}: no auto actions")
        proof = r.get("proof")
        if proof and not Path(str(proof)).exists():
            errs.append(f"{rid}: proof missing on disk: {proof}")
    if errs:
        print("\n".join(errs))
        print(f"\n{len(errs)} violation(s) across {len(records)} record(s)")
        return 2
    by_sev = {s: sum(1 for r in records if r.get("severity") == s) for s in SEVERITIES}
    print(f"{len(records)} risks valid (critical={by_sev['critical']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
