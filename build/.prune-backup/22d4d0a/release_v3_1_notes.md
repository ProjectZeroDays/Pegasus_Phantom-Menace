v3.1.0 — Full Architecture (12 Pillars)
1. Kernel (PASS) — deterministic replay, SQLite journal
2. Manifest (PASS) — target_manifest.schema.json + py
3. Oracle (PASS) — differential execution (oracle.py)
4. Phase engine (PASS) — PhaseGate typed gates
5. Blast radius (PASS) — shadow/assisted/autonomous
6. Mutation + Promotion (PASS) — provenance, shadow deploy
7. Self-healing (PASS) — supervisor, quarantine, revert
8. KB decay (PASS) — confidence, source, expiry
9. Idempotent (PASS) — wrapper, key
10. Why chain (PASS) — full trace, cost/phase
11. Safety/reversibility (PASS) — snapshot, dead-man
12. Human interface (PASS) — landing_merged.html, 5001
Repo: private. Port: 5001. Freeze: v3.0.0. Tests: 18 PASS.
