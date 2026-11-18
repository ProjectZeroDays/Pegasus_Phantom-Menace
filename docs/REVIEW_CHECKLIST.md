# Review checklist

## Route registration

Any route module added under `pegasus/ui/web/backend/` **must** have its
`register()` call in `create_app()`. Four modules were once written and never
registered, and that alone was the whole of the 30 HTTP failures in handoff 70.

`pegasus/tests/test_route_registration.py` enforces it - run it before review.

## Security posture

- [ ] New bind or listen surface documented in `docs/SECURITY.md`
- [ ] New write route behind the `confirm=true` gate if it changes system state
- [ ] No credential written into a tracked file
- [ ] Path parameters traversal-guarded

## Packaging

- [ ] `EXPECT_BUNDLE` updated if the bundle hashes moved
- [ ] Smoke run to `PACKAGED_233_OK` then `INSTALL_SMOKE_OK`
- [ ] No generated artefact staged; `dist/` stays untracked

## Honesty

- [ ] Limits of the feature recorded, not implied away
- [ ] A handoff written into `docs/PLAN.md`, never `docs/HANDOFF.md`
