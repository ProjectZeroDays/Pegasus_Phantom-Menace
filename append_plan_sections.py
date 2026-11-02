#!/usr/bin/env python3
"""Append §113–§126 to docs/PLAN.md and regenerate the handoff.

Numbering hole: §61–§112 are unallocated in this revision, so the block opens
with a reserved marker and resumes at §113.

Idempotent: refuses if §113 is already present.
"""
from pathlib import Path
import subprocess
import sys

PLAN = Path("docs/PLAN.md")

BLOCK = """
---

## 61–112. Reserved

Numbering resumes at §113. §61–§112 are unallocated in this revision and are not
referenced below.

---

## 113. Capability over platform

A module declares what it needs, never where it runs. A `platform ==` comparison
in a module body is a lint failure (§121). Host discovery resolves capabilities;
a capability with no provider fails at preflight, not mid-run. The adapter is the
only place that knows the platform.

---

## 114. Capability enum

`core/caps.py`, `class Cap(str, Enum)`, one member per capability, dotted
lowercase values (`file.get`, `creds.sam`). Manifests and transport `provides`
compare by value, never by member name. Parsing is AST (§123), so a docstring
edit or a reformat cannot change the set.

---

## 115. Module manifests

One YAML file per module under `post_exploitation/manifests/`. Required keys:
`id` `title` `category` `tier`. `requires_caps` maps `all` / `any` / `optional`
to cap values; at least one of `all` or `any` must be present. `depends_on`
names other module ids. Ids match `^[a-z][a-z0-9_]{2,23}$`.

---

## 116. Tiers

T1 reads, never mutates the host. T2 mutates with a documented undo. T3 persists
or pivots, and needs certified undo before `DESTRUCTIVE` runs (§28). A tier is a
ceiling on blast, not a promise of it.

---

## 117. Transport ABCs and leases

`Transport` ABC in `core/transport.py`, one adapter per provider. A capability
is held under a `Lease` with a TTL ceiling; expiry raises `LeaseExpired` rather
than retrying quietly. Sequencing lives in leases, not in callers.

---

## 118. Risk register

`risk/register.yaml`. Every record carries `detector`, `ladder`, `proof`,
`owner`, `sla_hours`. No risk without a detector; no detector without a proof
file. A proof is a skipped stub until it has failed green on its own.

---

## 119. modules_lint

Validates ids, tiers, caps, deps and cycles. Fails on an unknown cap, an orphan
cap, a phantom `provides` entry, and an unresolved dep. Sweeps the whole enum,
not only caps a manifest happens to reference. Exit 3 malformed tree, 2 any
violation.

---

## 120. risk_lint

Every record complete, every proof path present. Exit 3 missing register, 2 any
incomplete record.

---

## 121. no_platform_branch

Greps module bodies for `platform ==`. A branch is permitted only inside an
adapter. Exit 3 no modules yet, 2 branch found.

---

## 122. Capability matrix

`make caps-matrix` writes `build/caps_matrix.md` with a `STATUS: PASS|FAIL`
header, and `build/caps_matrix.json` for CI. Every cap names a transport or a
waiver. `build/caps_orphans.allow` takes `<cap>  # <reason>`; a waiver against a
cap that is provided reports as stale so it cannot outlive its cause.
`build/caps_baseline.json` records provider counts and a drop is reported.

---

## 123. caps_consistency

Runs `modules_lint` and `caps_matrix` and compares verdicts. Equal and zero
passes; equal and non-zero is the gate; unequal exits 3 with
`LINT DISAGREEMENT`. Both import `scripts/capreg.py`: one AST parser, one orphan
rule, two consumers. Agreement is structural, not a convention two files happen
to keep.

---

## 124. Derived audit

`audit_derive.py` computes the completion table from the tree; `--check` fails on
drift. Two columns, `unverified` and `implemented`; a T1/T2 module without a
fixture counts unverified, never implemented. `make audit` prints the split.

---

## 125. Gates G19–G21

G19 conformance, G20 modules-lint, G21 audit-check. Each has a deny and an admit
case (§60.14). G20 and the consistency gate run in `pre-push`.

---

## 126. P0 exit

All of: `build/map.diff` empty, §9.11 rows final, `make modules-lint` green,
`make caps-consistency` green, `make audit-check` green, `docs/HANDOFF.md` in
sync. Then `scripts/require.py P1`. Any one of these red keeps P0 open.
"""


def main() -> int:
    if not PLAN.exists():
        sys.exit("docs/PLAN.md missing")
    text = PLAN.read_text(encoding="utf-8")

    if "## 113." in text:
        print("§113 already present, nothing to append")
        return 0
    if "## 60." not in text:
        sys.exit("anchor §60 missing — refusing to append")

    if not text.endswith("\n"):
        text += "\n"
    PLAN.write_text(text + BLOCK, encoding="utf-8")
    print(f"appended {BLOCK.count(chr(10))} lines, PLAN.md now "
          f"{len(PLAN.read_text(encoding='utf-8'))} chars")

    gen = subprocess.run([sys.executable, "scripts/handoff.py"],
                         capture_output=True, text=True)
    print(f"handoff regenerate: exit {gen.returncode} {gen.stdout.strip()}")
    chk = subprocess.run([sys.executable, "scripts/handoff.py", "--check"],
                         capture_output=True, text=True)
    print(f"handoff --check:    exit {chk.returncode} {chk.stdout.strip()}")
    if chk.returncode:
        print("  " + (chk.stderr or "").strip()[:300])
    return chk.returncode


if __name__ == "__main__":
    sys.exit(main())