# phase-runner

Run one phase, in order, stopping at the first failure.

1. `make hooks` — re-assert hooksPath.
2. `make handoff` — regenerate the brief.
3. `python3 scripts/require.py <phase>` — exit 3 means stop and report the missing path.
4. `make <gate target>` — resolve via `skills/gate-map.md`.
5. On pass, write `docs/STATUS.md`.
6. On fail, print the phase revert from `build/phases.yaml` and stop.

Never continue on a red gate. Never use `--no-verify`. Never edit
`build/phases.yaml` to make a check pass.
