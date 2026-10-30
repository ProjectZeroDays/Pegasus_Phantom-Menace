# Changelog

All notable changes to Pegasus Phantom Menace. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] — 2026-10-30

Accounts, daemonisation, delivery tooling and full NSO-class parity.

### Added

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

- Dashboard rewritten: every counter and chart is sampled from the host or ADB,
  all buttons dispatch real endpoints, and pages stay reachable while exploit
  command internals remain redacted for unactivated accounts.
- Zero-click and post-exploitation suites now expose registries consumed by the
  CLI, dashboard and workflow engine.
- Web API `/api/commands/<name>/run` falls back to the slash-command surface, so
  every page button resolves.

### Fixed

- `access_workflow` package import is lazy, removing the plugin warm-up import
  deadlock.
- `c2_server` static route resolves absolutely; `telegram_control` long-poll no
  longer passes a duplicate `timeout` keyword.
- Session refresh order in auth so tier activation and last-login persist.

## [2.0.0] — 2026-10-30

The Web GUI release. Pegasus gains a complete operator console, the plugin
loader actually loads every module, and the web server is packaged as a
standalone Windows executable.

### Added

**Web GUI (`pegasus/ui/web`)**
- React 18 + TypeScript + Vite 6 single-page application, 32 feature pages,
  served by a Flask API from one process.
- Design system with dark mission-control styling, responsive layout down to
  phone width, installable PWA manifest.
- Application shell: grouped collapsible sidebar, active-device selector,
  live status bar, job drawer with streaming terminal output.
- **Mission Control** — merged from the two dashboard mockups: stat strip,
  device summary card, telemetry counts, quick command cards, workflow history,
  per-vector success rates, platform surface index.
- **Devices** — ADB inventory, full fingerprint inspector (40+ properties),
  live shell, wireless pairing (with code), bulk telemetry collection,
  device event feed.
- **Access Workflow** — 8 access vectors with availability, manual controls,
  autonomous lifecycle launch, stage visualisation.
- **Workflow Engine** — full-lifecycle and stage-by-stage runs, run history
  with stage inspection, per-vector success rates.
- **Zero-Click & CVE** — 6 exploit families (Pixel 8, S24, Xiaomi, OnePlus,
  AOSP, Android TV) and the 12-entry CVE database with live scoring.
- **Post-Exploitation** — 6-stage chain (fingerprint → persistence →
  credentials → lateral → exfiltration → harden), per-stage dispatch.
- **Telemetry pages** — Locations, Geofences (CRUD), Call Logs, Contacts,
  Messages, Browser (domain distribution), Applications, Photos & Video (with
  thumbnails and lightbox), Wi-Fi, Keystrokes, Activity Timeline, Keywords.
- **Operations pages** — Payloads (generation + artifact library),
  Wordlists (profile generator), Sessions (Metasploit RPC), Campaigns, Reports.
- **Network & tools** — nmap scanner with parsed host results, listener health,
  tunnel guidance, binary console, slash-command palette.
- **Skills Catalog** — 23 agent skill packs mapped to executable commands.
- **Plugins / Command Center / Settings** — registry views, all 40 commands
  dispatchable, workspace paths, environment and configuration reference.

**Backend (`pegasus/ui/web/backend`)**
- Flask application factory with ~90 routes and consistent
  `{"ok": bool, "data"|"error": ...}` envelopes.
- Background job manager: thread per job, progress, cooperative cancellation,
  bounded history, structured result capture.
- Output capture layer that unifies Python writes, file-descriptor writes and
  subprocess output, with Unicode-safe Rich rendering on Windows.
- Rich prompt shim that answers interactive modules from supplied values
  instead of blocking on stdin.
- Binary-safe media transfer via `adb exec-out` with a workspace cache and
  MIME sniffing.
- SQLite telemetry store (rolling samples, geofences, keywords, device notes)
  and 10 resilient ADB collectors.
- Platform event log persisted to the workspace logs directory.
- SPA fallback routing that keeps unknown `/api/*` paths as JSON 404s.

**Packaging**
- `pegasus_web.py` launcher, `Pegasus-Web.spec` PyInstaller spec and
  `version-web.txt` metadata; produces a single `dist/Pegasus-Web.exe`.
- `pegasus serve` / `pegasus web` CLI commands; legacy Flask C2 dashboard moved
  to `pegasus dashboard` on port 5050.
- Flask/CORS added to `requirements.txt` and `pyproject.toml`.

**Tests & docs**
- 24 pytest tests for the GUI backend (routing, registries, jobs, geofence and
  keyword CRUD, capture layer, telemetry store) — no device required.
- `pegasus/ui/web/README.md` with page map, full API reference and
  architecture notes; root and package READMEs updated.

### Fixed
- **Plugin loader never bound module-level metadata.** `plugin.py` files
  declare `metadata` at module level while the class lives in `module.py`, so
  10 of 14 plugins failed with `type object 'X' has no attribute 'metadata'`
  or `'NoneType' object has no attribute 'name'`. The loader now resolves the
  factory's target class (annotation, globals, closure) and binds metadata
  before instantiation. All 14 plugins and 40 commands now load.
- Plugin discovery returned duplicate paths, producing "already loaded"
  warnings; results are now de-duplicated by resolved path.
- Plugin async initialization used `get_event_loop()` and deadlocked when
  called from a thread with a running loop; replaced with a dedicated
  per-thread loop runner.
- `pegasus/pyproject.toml` contained invalid TOML (`per-file-ignores = {`
  spanning lines), which broke `pytest`, `ruff` and any TOML reader.
- Web launcher crashed on Windows consoles with `UnicodeEncodeError` when
  printing an arrow glyph; replaced with ASCII output.
- Every captured line was duplicated because the tee wrote to the original
  stream whose descriptor was already redirected; capture now writes once.
- Rich emitted cp437-era glyphs (`legacy_windows`) which arrived as mojibake
  in job output; legacy mode is disabled for the duration of a job.

### Changed
- `pegasus serve` now launches the real GUI (previously printed "available in
  Phase 3"); the old template dashboard is available as `pegasus dashboard`.
- `.gitignore` extended for Node modules, build caches and SQLite databases.

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
