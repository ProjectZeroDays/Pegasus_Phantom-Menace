# Pegasus Phantom Menace v2.1 — Web GUI

A complete operator console for the Pegasus platform: React + TypeScript + Vite
front end, Flask API back end, both living inside the Python package so a single
`pegasus serve` boots everything.

The design merges the two standalone dashboard mockups (`demo.html`,
`demo2.html`) into one application: the dark mission-control visual language,
the live device table, the stat strip, the command cards and the bottom status
bar, plus 30 real pages wired to the actual plugin system.

---

## Quick start

```bash
# 1 — build the front end (once, or after UI changes)
cd pegasus/ui/web
npm install
npm run build

# 2 — start the server
cd ../../..
python -m pegasus.ui.web.server --port 5000 --open
# or:  pegasus serve
```

Open <http://127.0.0.1:5000/>. The API is at `/api`, health at `/api/health`.

If the bundle has not been built yet the API still runs and `/` shows a build
notice instead of a blank page.

### Development mode (hot reload)

```bash
# terminal 1 — API
python -m pegasus.ui.web.server --port 5000

# terminal 2 — Vite dev server, proxies /api to :5000
cd pegasus/ui/web
npm run dev            # http://127.0.0.1:5173
```

Set `PEGASUS_API` to point the dev proxy at a different backend host.

---

## Architecture

```
pegasus/ui/web/
├── backend/
│   ├── app.py         Flask app factory, ~90 routes, SPA fallback
│   ├── jobs.py        job manager, captured output, prompt patching
│   ├── capture.py     stdout/stderr/FD capture + Rich console bridge
│   ├── tools.py       binary discovery, ADB helpers, environment probes
│   └── telemetry.py   SQLite sample store, geofences, keywords, collectors
├── server.py          CLI launcher (`python -m pegasus.ui.web.server`)
├── src/               React application
│   ├── App.tsx        route table
│   ├── nav.ts         navigation groups + skill catalogue
│   ├── state/         device + system context
│   ├── lib/           typed API client, formatting, telemetry hook
│   ├── components/    layout shell, sidebar, job drawer, UI kit
│   └── pages/         32 feature pages
├── tests/             pytest suite (24 tests, no device required)
└── dist/              built bundle served by Flask
```

### Request flow

```
Browser → GET /api/...            → Flask route
                                 → plugin_manager() (loaded once, warm)
                                 → jobs.submit(...)  → worker thread
                                 → StreamCapture wraps stdout/stderr/FD1-2
                                 → plugin command executes with Rich console
Browser → GET /api/jobs/<id>      → status + progress + captured output
```

Every blocking action returns **immediately** with a job id; the UI polls the
job and streams the terminal output live. Nothing in the UI ever waits on ADB,
nmap or msfvenom synchronously.

### Why jobs instead of synchronous routes

Pegasus modules are interactive CLIs. They call `Prompt.ask`, `Confirm.ask` and
print Rich tables. The job layer:

1. patches `rich.prompt.*` so prompts resolve from a supplied answer list
   instead of blocking on stdin (and logs the question + answer),
2. captures Python writes, descriptor writes and subprocess output in one
   buffer,
3. forces `legacy_windows=False` so Unicode table glyphs survive on Windows,
4. restores every patched global in a `finally` block.

---

## Pages

| Route | Page | What it drives |
|---|---|---|
| `/` | Mission Control | stat strip, active device card, telemetry counts, quick commands, workflow history, vector rates, platform surface |
| `/devices` | Devices | ADB inventory, fingerprint inspector, properties, live shell, wireless pairing, bulk collection |
| `/monitoring` | Monitoring | platform event log, job table, toolchain readiness, listener health, environment |
| `/access` | Access Workflow | 8 access vectors, manual controls, autonomous launch, vector telemetry |
| `/workflows` | Workflow Engine | full-lifecycle and stage-by-stage runs, run history, per-vector success rates |
| `/zero-click` | Zero-Click & CVE | zero-click families (Pixel 8, S24, Xiaomi, OnePlus, AOSP, TV) and the CVE table with live scanning |
| `/post-exploit` | Post-Exploitation | 6-stage chain with per-stage dispatch and progress |
| `/capabilities` | Capability Parity | 30 NSO-class capabilities with live parity scoring and direct invocation |
| `/locations` | Locations | GPS/fused location samples, filtering, live pull |
| `/geofences` | Geofences | create, toggle and delete perimeter zones |
| `/calls` | Call Logs | inbound/outbound/missed with talk-time meters |
| `/contacts` | Contacts | address book with phone/email facets |
| `/messages` | Messages | SMS stream with direction and unread filters |
| `/browser` | Browser | Chrome history with domain distribution |
| `/apps` | Applications | installed package inventory, grid/table |
| `/media` | Photos & Video | media index with live thumbnails and lightbox |
| `/wifi` | Wi-Fi Networks | known and visible networks |
| `/keylog` | Keystrokes | input queue stream |
| `/activity` | Activity Timeline | per-app usage plus platform events |
| `/keywords` | Keywords | keyword tracking and corpus scanning |
| `/payloads` | Payloads | msfvenom generation, artifact library, DNA/mutation/QR/SSL ops |
| `/wordlists` | Wordlists | profile-driven wordlist generation |
| `/sessions` | Sessions | Metasploit RPC session operations |
| `/campaigns` | Campaigns | campaign register and global stats |
| `/reports` | Reports | HTML/JSON report build and archive |
| `/network` | Network Scanner | nmap discovery, listener health, tunnels |
| `/tools` | Toolbox | direct binary console + full slash-command palette |
| `/skills` | Skills Catalog | 23 agent skill packs with linked commands |
| `/plugins` | Plugins | loaded plugins, commands and UI contributions |
| `/commands` | Command Center | all 40 registered commands with dispatch |
| `/settings` | Settings | workspace paths, environment, services, env vars |

---

## API reference

All responses are `{"ok": true, "data": ...}` or `{"ok": false, "error": ...}`.

### System
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness, version, uptime |
| GET | `/api/system` | components, workspace, environment, job stats |
| GET | `/api/system/tools` | 14-binary toolchain inventory |
| GET | `/api/system/environment` | host/OS/python details |

### Plugins & commands
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/plugins` | plugin catalogue with commands + components |
| GET | `/api/plugins/<name>` | single plugin detail |
| GET | `/api/commands` | flat command registry |
| POST | `/api/commands/<name>/run` | dispatch a plugin command → job |
| GET | `/api/slash-commands` | slash command palette |
| POST | `/api/slash-commands/<name>/run` | dispatch a slash command → job |
| POST | `/api/slash-commands/<name>/toggle` | enable/disable |

### Jobs
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/jobs` | recent jobs + stats |
| GET | `/api/jobs/<id>` | job detail with output (`?tail=N`) |
| POST | `/api/jobs/<id>/cancel` | cooperative cancellation |

### Devices & telemetry
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/devices` | ADB inventory with fingerprints |
| GET | `/api/devices/<serial>` | full device detail |
| POST | `/api/devices/connect` | `adb connect` |
| POST | `/api/devices/disconnect` | `adb disconnect` |
| POST | `/api/devices/pair` | wireless pairing → job |
| POST | `/api/devices/<serial>/shell` | shell command → job |
| POST | `/api/devices/<serial>/collect` | bulk telemetry → job |
| GET | `/api/devices/<serial>/dashboard` | summary counts and tops |
| GET | `/api/devices/<serial>/telemetry/<kind>` | contacts, sms, calls, browser, apps, media, wifi, locations, activity, keylog |
| GET | `/api/devices/<serial>/media/<id>/<variant>` | binary media (`thumb`/`raw`) |
| GET/POST | `/api/devices/<serial>/geofences` | list / create zones |
| PATCH | `/api/geofences/<id>/toggle` | toggle a zone |
| DELETE | `/api/geofences/<id>` | delete a zone |
| GET/POST | `/api/devices/<serial>/keywords` | list / add keywords |
| POST | `/api/devices/<serial>/keywords/scan` | match corpus |
| DELETE | `/api/keywords/<id>` | remove keyword |

### Operations
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/stages` | 12 stages, 2 categories, 18 vectors |
| GET | `/api/workflows` | run history + success rates |
| POST | `/api/workflows/run` | launch lifecycle run → job |
| GET | `/api/cve` | built-in CVE database |
| POST | `/api/cve/scan` | device CVE scan → job |
| GET | `/api/payloads` | payload artifacts |
| POST | `/api/payloads/generate` | msfvenom generation → job |
| POST | `/api/passgen` | wordlist generation → job |
| GET | `/api/reports` | report archive |
| GET | `/api/reports/<name>` | download a report |
| POST | `/api/reports/generate` | build a report → job |
| GET/POST | `/api/campaigns` | campaign register |
| GET | `/api/listeners` | local port probe |
| POST | `/api/network/scan` | nmap scan → job |
| POST | `/api/tools/<key>/run` | run an allow-listed binary → job |
| GET/POST | `/api/activity` | platform event log |

---

## Telemetry store

`<workspace>/telemetry.db` (SQLite) holds:

* `samples` — rolling snapshots per device and kind (40 kept each),
* `geofences` — zones with radius and active state,
* `keywords` — tracked terms with hit counters,
* `device_notes` — operator labels, groups and notes.

Collectors read Android providers with `adb shell content query` and parse both
the CLI row format and quoted multi-line values. Chrome history is pulled from
the on-device database (root `cp` or `run-as`) and read read-only. Every
collector degrades to an empty list — a missing provider never raises.

---

## Testing

```bash
python -m pytest pegasus/ui/web/tests -q      # 24 tests
cd pegasus/ui/web && npm run typecheck        # TS strict mode
```

The suite covers health, system, plugin/command registries, the stage catalogue,
the CVE database, tool scanning, the SPA and its client-route fallback, JSON
404s for unknown API routes, job dispatch, geofence CRUD, keyword lifecycle,
Unicode-safe output capture and telemetry store round-trips. No device required.

---

## Operational notes

* **Plugin loading is lazy and warmed in a thread.** The first `/api/plugins`
  call never blocks the UI while 14 plugins import.
* **Metadata binding.** `plugin.py` modules declare `metadata` at module level
  while the class lives in `module.py`; the loader now binds module metadata to
  the factory's target class before instantiation, which is what makes all 14
  modules load instead of 4.
* **Prompt patching is global** (`rich.prompt`), so jobs are serialized by
  design where they call prompts. Non-interactive commands can run in parallel.
* **CORS is open for `/api/*`** so the Vite dev server and mobile WebView can
  talk to the backend.
* **Media is cached** in `<workspace>/media_cache` and fetched with `exec-out`
  so binary payloads are not corrupted by terminal encoding.

## License

MIT — see the repository `LICENSE`.
