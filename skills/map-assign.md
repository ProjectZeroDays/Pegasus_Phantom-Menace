# map-assign

Close `build/map.diff` to zero.

1. `make map` — writes `build/map.diff`.
2. Choose one verdict per line: KEEP MOVE MERGE DELETE ARCHIVE VENDOR GENERATE.
3. Add a row to PLAN section 9 with the verdict and a one-line reason.
4. Re-run `make map`. Repeat until empty.

Assign section 9.11 groups first. Never delete without a row.
