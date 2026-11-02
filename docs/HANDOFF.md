## 60. Handoff notes for the coding agent

Generated into `docs/HANDOFF.md`. Edit this section, never the generated file.

1. **`bash bootstrap.sh` once.** Writes tooling, hooks and adapters, sets hooksPath, runs the sequence. Re-run without `--force` is safe.
2. **`make hooks` after any fresh clone or pull.**
3. **Prefer `/phase <id>`** over remembering the steps.
4. **Snapshot OpenAPI and routes before touching `dashboard_server.py`.** P3b pins the hashes.
5. **R0 does not exit until `build/map.diff` is empty.** Assign §9.11 first.
6. **Diff each root entrypoint against `__main__` before archiving.** Write `DIFF.md`.
7. **`python3 scripts/require.py <phase>` before every phase.** Exit 3 means stop.
8. **Never edit `build/phases.yaml` to unblock yourself** without `PLAN:` + `make plan-lint`.
9. **Six core modules before any import rewrite.**
10. **Delete, do not comment out.**
11. **`archive/` and `vendor/` stay out of the package.**
12. **CSRF gate lands `xfail`, flips blocking in P6.**
13. **A red `main` is fixed before any feature commit.**
14. **Every gate needs a deny and an admit case.**
15. **`PARTIAL` is a success status** — always a reason.
16. **Every module declares `blast` and `schema`.**
17. **Undo at 5.5, before execution.** `DESTRUCTIVE`+ without certified undo does not run.
18. **Nothing merges without the harness.**
19. **Uncited AI claims are `None`.**
20. **The judge never holds sole authority.**
21. **Fence target content as `UNTRUSTED`.**
22. **An expired pin blocks judging.**
23. **Secrets never enter the journal.**
24. **Report status in `docs/STATUS.md`** using the §40 format.
25. **Stop at the first gate failure and print the revert.**
26. **Commit prefixes are enforced** — `P3b: extract blueprints`.
27. **Never hand-edit a generated adapter.** Edit `skills/agents.yaml`, run `make agents`.
28. **If a hook blocks you, fix the cause.** `pre-push` and CI catch `--no-verify` anyway.
29. **If §60 changes, the hook regenerates HANDOFF — confirm `git diff --cached` shows both files.**

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
