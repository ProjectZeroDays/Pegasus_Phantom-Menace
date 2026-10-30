# Pegasus Phantom Menace v2 — Architecture

This document describes how the platform is put together, where each
responsibility lives, and the non-obvious decisions behind the structure.

---

## 1. Layers

```
┌──────────────────────────────────────────────────────────────┐
│  Front end — pegasus/ui/web/src (React 18 + TS + Vite 6)    │
│  32 pages · app shell · job drawer · typed API client        │
└───────────────────────────┬──────────────────────────────────┘
                            │  JSON over /api  (same origin)
┌───────────────────────────▼──────────────────────────────────┐
│  API — pegasus/ui/web/backend (Flask 3)                     │
│  routes · job manager · capture · telemetry store · probes   │
└───────────────────────────┬──────────────────────────────────┘
                            │  in-process imports
┌───────────────────────────▼──────────────────────────────────┐
│  Platform — pegasus/core + pegasus/modules                   │
│  config · plugin system · db · 14 modules · workflow engine  │
└───────────────────────────┬──────────────────────────────────┘
                            │  subprocess / sockets
┌───────────────────────────▼──────────────────────────────────┐
│  Toolchain — adb · fastboot · nmap · msfvenom · frida · …    │
└──────────────────────────────────────────────────────────────┘
```

The GUI adds no parallel business logic: it invokes the same plugin commands
the CLI invokes. Anything the CLI can do, the GUI can do, with identical
output.

---

## 2. Plugin system

### The contract

```
pegasus/modules/<name>/
├── plugin.py    metadata = PluginMetadata(...)   create_plugin(context) -> Module
└── module.py    class <Name>Module(BaseModule)   commands, UI components, hooks
```

`PluginManager.discover_plugins()` walks every configured directory and finds
`plugin.py` files (de-duplicated by resolved path).

### Loading, step by step

1. Import `plugin.py` under a spec-derived module object.
2. Read module-level `metadata` (a `PluginMetadata`).
3. Skip if already loaded; verify `requires` imports and `conflicts`.
4. **Bind metadata**: the concrete class lives in `module.py`, so it has no
   `metadata` of its own. The loader resolves the factory's target class via
   return annotation → factory globals → closure cells, then assigns
   `cls.metadata = metadata` *before* instantiation, because `BaseModule.__init__`
   reads `self.metadata.name` to build its logger.
5. Instantiate via the factory.
6. Run `initialize()` on a dedicated event loop (`_run_async`), which is safe
   even when a loop is already running on the calling thread.
7. Register commands, UI components and hooks into `AppContext`.

Step 4 is the fix that took the platform from 4 loaded plugins to 14.

### Registry

`AppContext` holds `plugins`, `commands`, `ui_components` and `hooks`. Commands
are keyed by name with alias entries, so `/api/commands` and the CLI share one
source of truth (40 commands across 14 plugins).

---

## 3. Job pipeline

Long operations cannot run inside a request. `JobManager` gives each one a
thread and an id:

```
POST /api/commands/<name>/run
      └─ jobs.submit(kind, title, fn, meta, answers)  →  { job: { id, status: queued } }

thread:
      StreamCapture.__enter__()
        ├─ rich.console.WINDOWS = False        (Unicode glyphs preserved)
        ├─ sys.stdout/stderr → string buffer   (Python writes)
        └─ os.dup2(tmpfile, 1 and 2)           (fd writes, subprocess output)
      patch rich.prompt.{Prompt,Confirm,IntPrompt}
        └─ answers resolved from a supplied list; question + answer logged
      plugin callback(*argv)  (async results awaited on a private loop)
      capture.__exit__()  → flush, restore streams/flag, restore prompts
      job.status = succeeded | failed | cancelled
```

`GET /api/jobs/<id>` returns status, progress, duration, captured output and
the structured result. The UI polls at 900 ms while a job is live.

Why patch prompts globally: Pegasus modules call `Prompt.ask` directly. Altering
their code to accept injected input would touch 14 modules; patching the three
Rich entry points keeps the modules untouched and their CLI behaviour intact.

Consequence: jobs that prompt are effectively serialized. Commands without
prompts (shell, connects, scans) run concurrently without issue.

---

## 4. Output capture

Three output paths must be unified, or the terminal view loses text:

| Source | Example | Mechanism |
|---|---|---|
| Python writes | `print`, Rich consoles | `sys.stdout` replacement |
| fd writes | C extensions, `os.write` | `dup2` into a temp file |
| child processes | `subprocess.run(...)` | inherits fd 1/2 → same temp file |

The original implementation teed Python writes to the old stream *and* captured
its descriptor, duplicating every line. The current version writes Python output
only to the string buffer, and descriptor output only to the temp file, then
concatenates.

Rich's `legacy_windows` flag substitutes cp437 characters for box drawing,
which json-encodes fine but renders as mojibake in the browser. It is disabled
for the duration of a job and restored afterwards, including on already-created
`Console` instances found in loaded modules.

---

## 5. Telemetry

`<workspace>/telemetry.db` (SQLite) is the cache and the user-data store:

- `samples(serial, kind, payload, collected_at)` — rolling JSON snapshots,
  40 retained per device/kind.
- `geofences(id, serial, name, lat, lng, radius_meters, is_active, created_at)`.
- `keywords(id, serial, keyword, hit_count, last_hit_at, created_at)`.
- `device_notes(serial, label, group_name, notes, updated_at)`.

Collectors (`telemetry.COLLECTORS`) map a kind to a function that reads an
Android provider over ADB:

| kind | source |
|---|---|
| contacts | `content://com.android.contacts/data/phones` |
| sms | `content://sms` |
| calls | `content://call_log/calls` |
| browser | pulled Chrome `History` (root `cp` or `run-as`) |
| apps | `pm list packages -3 -f` + `dumpsys package` |
| media | `content://media/external/{images,video}/media` |
| wifi | `dumpsys wifi`, `cmd wifi list-scan-results` |
| locations | `dumpsys location` |
| activity | `dumpsys usagestats` |
| keylog | `dumpsys input` |

Parsing handles the `Row: N key=value, key="value, with comma"` format with a
quote-aware splitter, and multi-line bodies. Each collector is wrapped so a
missing provider yields `[]`, never an exception. Reads are cached; `?refresh=1`
forces a live pull.

Media bytes bypass the text pipeline entirely (`adb exec-out` → file), because
`adb shell` translates line endings and corrupts binary data.

---

## 6. Front end

**No global store beyond two contexts.** `AppProvider` holds devices, the active
serial (persisted in localStorage) and system health, polling every 20–30 s.
Every page fetches what it needs through `useApi`, which handles loading, error,
interval polling and manual refresh.

**Design system** lives in `index.css` as CSS custom properties plus a small
component kit (`Panel`, `Badge`, `Stat`, `Segmented`, `Terminal`, `Modal`,
`Empty`, `Loading`). Tailwind v4 is present for utility use, but the layout
classes are semantic so the visual language stays coherent.

**Navigation** is data-driven (`src/nav.ts`): one array of groups and items
drives the sidebar, the route table references the same pages, and Mission
Control's platform index renders from it.

**Types mirror the API exactly** (`src/lib/types.ts`), so a backend shape change
is a compile error rather than a runtime blank.

---

## 7. Packaging

`Pegasus-Web.spec` bundles:

- the Python package (core, modules, plugins, `pegasus/ui/web/backend`),
- the built SPA (`pegasus/ui/web/dist`) as data,
- access-workflow templates/static assets and the web icon,
- hidden imports for lazily imported modules (workflow engine, campaign manager,
  RAT, analysis, integrations, and the module implementations).

Unused heavyweight libraries (tkinter, numpy, pandas, matplotlib, Qt, pytest)
are excluded. Output: one `dist/Pegasus-Web.exe` with version metadata and icon.

`pegasus_web.py` resolves `sys._MEIPASS` when frozen so bundled resources are
found, then delegates to the same `create_app()` used in development.

---

## 8. Decisions worth knowing

1. **Flask, not FastAPI** — the dashboard service already depended on Flask, and
   the GUI needs synchronous plugin calls plus a static SPA. One process, one
   port, no ASGI bridge.
2. **Jobs, not streaming websockets** — polling at 900 ms is indistinguishable
   in practice and survives proxies, sleep/wake and multiple tabs. Output is
   bounded per job.
3. **SQLite for telemetry, SQLAlchemy for platform data** — the platform's
   async SQLAlchemy models serve long-lived entities; telemetry is high-churn
   snapshots that benefit from a dependency-free local store.
4. **Patch Rich rather than refactor modules** — preserves CLI behaviour exactly
   and keeps the GUI a pure consumer of module code.
5. **One navigation array** — sidebar, routes and index share a definition, so
   adding a page is one entry plus one component.
6. **Binary media over `exec-out`** — the only reliable way to move bytes off an
   Android device without corruption.

---

## 9. Extending

**Add a page.** Create `src/pages/MyPage.tsx`, add a `Route` in `App.tsx`, add
an entry to `NAV_GROUPS` in `nav.ts`.

**Add a backend endpoint.** Add the route inside `create_app()` using the
`ok()`/`fail()` helpers; put long work behind `jobs.submit`.

**Add a module.** Follow the `plugin.py` + `module.py` contract; register
commands in `_register_commands` and a UI component path. It appears in
`/api/plugins` and the Command Center automatically.

**Add a telemetry kind.** Write a collector, register it in `COLLECTORS`, and
the generic `/telemetry/<kind>` endpoint serves it.

## Delivery page
`/delivery` exposes the 17 intent channels, payload server, transcript preview, carrier catalog and send history. Backed by `pegasus/modules/access_workflow/delivery.py` and `catalog.py`; see `docs/DELIVERY.md`.
