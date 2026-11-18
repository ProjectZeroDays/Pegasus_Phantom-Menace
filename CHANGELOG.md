# Changelog

All notable changes to Pegasus Phantom Menace. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.4] — 2026-11-18

The console's C2 surface is now wired through the main backend and the Python tree compiles and lints clean.

### Added

- **C2 console routes** — `pegasus/ui/web/backend/c2_routes.py`: Start/Stop/Kill/Beacon endpoints POST to the real listener in `pegasus.modules.c2.server`. Bind posture is loopback by default (`PEGASUS_C2_HOST`), the `/api/c2/start` host argument is validated against wildcard/loopback sentinels plus the machine's own interface addresses, and `PEGASUS_C2_TLS` enables TLS for `wss://` clients. Autostart runs from `start_server.py` after the main socket is listening.
- **Q9 capability surface** — `q9_routes.register(...)` in `create_app()`: the 84 Q9 endpoints defined since the Q9 integration (previously every `/api/q9/*` path 404'd) are now routable. `_wipe_traces()`, `_local_base()` and the missing `zlib` import are implemented; `test_route_registration.py` fails the build if a declared route is not registered.
- **Contract tests** — `test_c2_routes_contract.py` covers C2 status/start/kill/beacon validation and host resolution; `test_route_registration.py` statically checks every `*_routes.py` path is served.
- **Docs** — `docs/C2.md`, `docs/SECURITY.md`, `docs/REVIEW_CHECKLIST.md`.
- **Repo hygiene** — `.github/dependabot.yml` (electron, pegasus-desktop, web UI, pip, github-actions); `.gitignore` secret-material rules; `.secret-hygiene-tmp/`.

### Fixed

- Syntax repairs: `access_workflow/agent/factory.py` (unterminated string in skill install check), `pwa/service_worker.py` and `webhook/webhook_server.py`, `pdf_generator.py`, `social_media.py` (docstring quotes, dataclass annotations, stray quotes), `ui/web/api/social_media.py` (unterminated docstrings), `qandroid_inferor_complete.py` (unterminated f-string, dead `tasks_main` call).
- `mitm/module.py` — Frida method-trace payload used single-brace `{className}`/`{methodName}` inside an f-string (runtime `NameError`); replaced with JS string concatenation.
- `ui/web/backend/app.py` — missing `get_settings` import and `Response` return annotations; console now binds loopback unless `PEGASUS_HOST` is set.
- `pwa/manifest.py` — missing `Any` import and `logger` definition; `pegasus/modules/social_media.py` — latent `NameError` for `timeframe_hours` in `_generate_summary`.
- **Credential scrub** — `weapons/PoCGen/config/config.py` and its README: hardcoded LLM provider URLs and API keys replaced with environment placeholders. (Keys are still in git history; `secret_hygiene.py --rewrite` handles the gated history rewrite separately.)
- `.githooks/commit-msg` — phase-prefix pattern `P[0-9]+[a-c]?` so two-digit phases pass.

### Notes

- `pegasus/ui/web/src/lib/accent.ts` is committed as build-required source (guard added to `.gitignore`); the web console rebuilt cleanly (`tsc --noEmit` + `vite build`), 390 routes probed with no duplicates, 57/57 tests pass.
- The dependency advisory triage from earlier 2.3.x releases carries forward; `weapons/` advisories remain tracked separately (see docs/PLAN.md).

## [2.2.0] — 2026-11-10

Enterprise build completed on top of the 2.1.0 production baseline. Web console gained full enterprise surfaces and defensive ML/blockchain/quantum modules; release tooling moved to a single 2.2.0 version across all packaging surfaces.

### Added

- **Phases 15-21 enterprise glue** — web console pages and REST endpoints for social-media OSINT collection (catalog, campaigns, intel store), cloud relay tunnel management, PWA offline support, multi-tenant RBAC (owner/admin/editor/viewer), HMAC-SHA256-signed webhooks with in-memory registry + JSONL event log, and authorized simulated-phishing awareness campaigns (draft-only launch).
- **Phase 22 Machine Learning** — EWMA z-score anomaly gate, order-2 n-gram behaviour predictor, severity-tiered dry-run response planner, JSONL operator-feedback store (threshold tuning).
- **Phase 23 Blockchain** — read-only JSON-RPC ERC-20 helpers (eth_call), SHA-256 Merkle trees with inclusion proofs, content-addressed store with optional IPFS pinning, local token ledger (balances, quotas, audit).
- **Phase 24 Quantum** — BB84 QKD simulation with intercept-resend detection, hybrid HKDF-SHA256 key derivation, PQC migration audit mapping RSA/DSA/ECC/DH/MD5/SHA-1 to NIST FIPS 203/204/205, quantum-resistant baseline check, experimental single-use Lamport OTS.
- **GUI redesign visual spec** — `gui-demo.html` (48 pages, single token system).

### Fixed

- `commands.py:300` — unterminated string literal in `cmd_payload_mass` argument parsing (SyntaxError).
- `relay/__init__.py` — stub `relay_routes` class in `loadbalancer.py` shadowed the real Flask adapter; `/api/relay/*` routes now register.
- `social_engineering/social_server.py` — six corrupted string literals repaired.
- Adopted `pegasus/VERSION` as canonical version source (2.2.0); aligned pyproject, web package.json, electron package.json and pyinstaller version resources.

### Removed

- `pymetasploit3` (unused; 2 known vulnerabilities).

### Notes

- BB84 is a simulation over classical RNG; Lamport signatures are single-message; the local ledger is not a blockchain; PQC audit does not ship liboqs; social-engineering campaigns are draft-only. Integration tests cover route registration (127 rules) — quantum/blockchain/ML modules are import-verified, pending functional test coverage.

## [2.1.0] — 2026-10-30

Accounts, daemonisation, delivery tooling, full NSO-class parity and the
productionised web GUI.

### Added

- **Web GUI productionised** — the React/TypeScript console is now packaged
  into the Python tree (`pegasus/ui/web`) and served by `pegasus serve` from a
  single process, with a standalone `Pegasus-Web.exe` launcher.
  - 33 pages: Mission Control, Devices, Monitoring, Access Workflow, Workflow
    Engine, Zero-Click & CVE, Post-Exploitation, Capability Parity, Delivery,
    Locations, Geofences, Calls, Contacts, Messages, Browser, Applications,
    Media, Wi-Fi, Keystrokes, Activity, Keywords, Payloads, Wordlists,
    Sessions, Campaigns, Reports, Network Scanner, Toolbox, Skills, Plugins,
    Command Center, Settings.
  - Background job pipeline with streamed terminal output, progress and
    cancellation for every ADB, nmap, msfvenom and lifecycle action.
  - ADB telemetry collectors (contacts, SMS, calls, Chrome history, apps,
    media, Wi-Fi, GPS, usage, input) cached in `<workspace>/telemetry.db`
    alongside geofences, keyword tracking and device notes.
  - Binary-safe media transfer via `adb exec-out`, MIME sniffing and a
    workspace cache.
  - `/api/nso/capabilities`, `/api/nso/run/<capability>` and
    `/api/nso/manifest` endpoints backing the parity page.
  - 30 backend tests covering routing, registries, jobs, CRUD, capture
    semantics, telemetry and the frozen-bundle loader.
- **Accounts and billing** — first-run admin bootstrap (password, passkey,
  optional FIDO2), self-service registration with an admin approval queue,
  USDC one-time/weekly/monthly access, on-chain verification through Blockscout
  and manual operator override. Demo account `demo` / `demo`.
- **Daemon** — supervised dashboard process with health checks, exponential
  backoff, Windows service (NSSM) and scheduled-task installation, plus
  uninstall/startup scripts.
- **Installer** — NSIS package with virtualenv creation, PATH launcher, service
  or task component and clean uninstall.
- **Global command factory** — 28 commands across agents, skills, custom
  commands, MCP servers, plugins, extensions and workflows, sourced from Quantum
  CLI/C2 and desktop skill folders.
- **Delivery tooling** — AI mutation engine, mass payload generator, payload DNA
  registry, LSB steganography and Telegram remote control.
- **FRP unlock facade** with a method plan and adaptive chain.
- **NSO-class capability registry** — 30 capabilities mapped to live callables,
  parity endpoint, CLI assertion, and run buttons in the console.

### Changed

- `pegasus serve` launches the real GUI; the legacy template dashboard moved to
  `pegasus dashboard` on port 5050.
- Dashboard rewritten: every counter and chart is sampled from the host or ADB,
  all buttons dispatch real endpoints, and pages stay reachable while exploit
  command internals remain redacted for unactivated accounts.
- Zero-click and post-exploitation suites now expose registries consumed by the
  CLI, dashboard and workflow engine.
- Web API `/api/commands/<name>/run` falls back to the slash-command surface, so
  every page button resolves.

### Fixed

- **Plugin metadata binding** — module-level `metadata` was never attached to
  the class in `module.py`, so 10 of 14 plugins failed to load
  (`type object 'CVEScannerModule' has no attribute 'metadata'`). The loader
  resolves the factory's target class and binds metadata before instantiation:
  4 → 14 plugins, 16 → 40 commands.
- **Frozen-bundle plugin loading** — with no `plugin.py` on disk the loader
  found nothing; it now falls back to importing the built-in module packages.
- Plugin discovery de-duplicated by resolved path; async initialisation no
  longer deadlocks on an already-running loop.
- Invalid TOML in `pegasus/pyproject.toml` (`per-file-ignores` block) that
  broke pytest/ruff for the whole repository.
- Windows launcher `UnicodeEncodeError` on arrow glyphs at startup.
- Job output was duplicated line-by-line and truncated table cells; capture now
  writes once, keeps Unicode box drawing, and uses a 180-column width.
- `access_workflow` package import is lazy, removing the plugin warm-up import
  deadlock.
- `c2_server` static route resolves absolutely; `telegram_control` long-poll no
  longer passes a duplicate `timeout` keyword.
- Session refresh order in auth so tier activation and last-login persist.

## [2.0.0] — 2026-10-30

Web GUI foundation.

### Added

- React 18 + TypeScript + Vite 6 console (`pegasus/ui/web`) with a Flask API
  served from one process, dark mission-control design system, responsive
  layout and an installable PWA manifest.
- Application shell: grouped collapsible sidebar, active-device selector, live
  status bar and a job drawer with streaming terminal output.
- Page set: Mission Control, Devices, Monitoring, Access Workflow, Workflow
  Engine, Zero-Click & CVE, Post-Exploitation, Locations, Geofences, Calls,
  Contacts, Messages, Browser, Applications, Photos & Video, Wi-Fi, Keystrokes,
  Activity, Keywords, Payloads, Wordlists, Sessions, Campaigns, Reports,
  Network Scanner, Toolbox, Skills Catalog, Plugins, Command Center, Settings.
- Background job manager with output capture, progress and cancellation; ADB
  telemetry store (samples, geofences, keywords, device notes) and 10 resilient
  collectors.
- `pegasus_web.py` launcher, `Pegasus-Web.spec` packaging spec and
  `version-web.txt` metadata producing a single `dist/Pegasus-Web.exe`.
- `pegasus/ui/web/README.md` (page map, API reference, architecture) and
  `docs/WEB_GUI_ARCHITECTURE.md`.

### Fixed

- Plugin loader never bound module-level metadata to the class in `module.py`,
  so most modules failed to load.
- Duplicate plugin discovery, and an async-init deadlock when a loop was
  already running on the calling thread.
- Invalid TOML in `pegasus/pyproject.toml` that broke pytest and ruff.
- Windows launcher `UnicodeEncodeError` on arrow glyphs.
- Duplicated and truncated job output (tee double-write, default console
  width).

---

## [1.4.0] — 2026-05-07

### Added
- Latent feature module (Pegasus v1.4 payload source).
- Windows executable with embedded version info and icon.

---

## [1.3.0]

### Added
- Editable payload source (`payload_src_1.3.py`) and rebuild tooling.

---

## [1.2.0]

### Added
- Network pairing and ADB scan options (24/25).

---

## [1.1.0]

### Added
- Initial device management CLI.

---

## [1.0.0]

- Initial release.
