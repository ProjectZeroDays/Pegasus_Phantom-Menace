# blocked-recovery

1. Read the failure verbatim.
2. Classify: precondition (exit 3), gate failure (exit 2), environment.
3. Precondition — satisfy it, do not edit `phases.yaml`.
4. Gate failure — fix the cause; if the gate is wrong, propose an ADR.
5. Re-run the same gate and report the diff.
6. Continue only after green.

Do not delete a check, skip a test, or use `--no-verify`.
