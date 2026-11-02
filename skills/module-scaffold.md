# module-scaffold

1. `make caps-matrix` — every cap you need must name a transport.
2. `make modules-lint` — must pass.
3. Add the manifest entry with `requires_caps` (values, not names) and a tier.
4. `make module-new ID=<id>` for the body, if T1 or T2.
5. Write the replay fixture.
6. `make contract` then `make audit`.

T1 with no fixture stays `unverified`. Never set T1/T2 without a method. A cap
with no provider needs a line in `build/caps_orphans.allow`, or the build stops.
