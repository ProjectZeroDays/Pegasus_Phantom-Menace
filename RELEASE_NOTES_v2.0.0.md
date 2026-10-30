# Pegasus Phantom Menace v2.0.0 — Web GUI release

**Release date:** 2026-10-30

Pegasus now ships with a full operator console: 32 pages of React/TypeScript
driving the real plugin system through a Flask API, packaged as a standalone
Windows executable. The plugin loader also gained a real fix — all 14 modules
and 40 commands load now, where 4 modules used to fail silently.

---

## Download

| Asset | What it is | Requirements |
|---|---|---|
| **`Pegasus-Web.exe`** | Standalone web GUI launcher — bundles the Flask API and the built SPA | Windows 10+ · no Python needed |
| `Pegasus-v1.4.exe` | Legacy CLI tool | Windows 10+ |
| Source archive | Full repository (Python package + front end) | Python 3.11+, Node 20+ (to rebuild the UI) |

`Pegasus-Web.exe` starts the server on <http://127.0.0.1:5000> and opens your
browser. Use `--port`, `--host 0.0.0.0` or `--no-browser` to change behaviour.

---

## Highlights

- **Mission Control** — the two dashboard mockups merged into one live
  overview: stat strip, device card, telemetry counts, quick commands,
  workflow history, per-vector success rates.
- **Live job pipeline** — every action (ADB shell, nmap, msfvenom, lifecycle
  runs, report builds) runs as a background job with streaming output,
  progress and cancellation. Nothing in the UI blocks.
- **Real device telemetry** — contacts, SMS, call logs, Chrome history,
  installed apps, media, Wi-Fi and GPS pulled over ADB, cached in a local
  SQLite store alongside geofences, keyword tracking and device notes.
- **Complete command surface** — all 40 plugin commands and 46 slash commands
  are browsable and executable with the same output the CLI prints.
- **Toolchain awareness** — 14 external binaries probed with version and
  availability, driving readiness badges across the UI.
- **Full access/exploitation workflow** — 8 access vectors, 12 lifecycle
  stages, 6 zero-click families, 12-entry CVE database, 6-stage
  post-exploitation chain.
- **PWA-ready** — installable on desktop and mobile, responsive to phone width.

---

## Page map

| Area | Pages |
|---|---|
| Command | Mission Control · Devices · Monitoring |
| Access & exploitation | Access Workflow · Workflow Engine · Zero-Click & CVE · Post-Exploitation · Capability Parity |
| Device data | Locations · Geofences · Call Logs · Contacts · Messages · Browser · Applications · Photos & Video · Wi-Fi · Keystrokes · Activity Timeline · Keywords |
| Operations | Payloads · Wordlists · Sessions · Campaigns · Reports |
| Network & tools | Network Scanner · Toolbox · Skills Catalog |
| System | Plugins · Command Center · Settings |

---

## Fixed in this release

1. **Plugin metadata binding** — module-level `metadata` was never attached to
   the class defined in `module.py`, so 10 of 14 plugins failed to load
   (`type object 'CVEScannerModule' has no attribute 'metadata'`). The loader
   now resolves the factory's target class and binds metadata before
   instantiation. Result: 4 → 14 plugins, 16 → 40 commands.
2. **Duplicate plugin discovery** — paths are de-duplicated before loading.
3. **Async init deadlock** — plugin initialization no longer uses
   `get_event_loop()`; it runs on a dedicated per-thread loop.
4. **Invalid TOML** — `pegasus/pyproject.toml` had a malformed
   `per-file-ignores` entry that broke pytest/ruff for the whole repo.
5. **Windows console crash** — the launcher no longer prints non-cp1252 glyphs.
6. **Duplicated job output** — capture now records each line exactly once.
7. **Mojibake in job output** — Rich's `legacy_windows` substitution is
   disabled during capture, so table borders render correctly.

---

## Upgrading

```bash
git pull
pip install -r pegasus/requirements.txt
cd pegasus/ui/web && npm install && npm run build
python -m pegasus.ui.web.server --port 5000 --open
```

No database migration is required: the telemetry store is created on first run
at `<workspace>/telemetry.db`.

---

## Verifying this release

```bash
python -m pytest pegasus/ui/web/tests -q      # 24 passed
cd pegasus/ui/web && npm run typecheck        # clean
```

Manual smoke test: open the GUI, confirm the footer shows **14 plugins · 40
commands**, run any command card and watch the terminal stream.

---

## Known limitations

- Interactive module flows are answered from queued values, so a command with
  many free-text prompts is better driven from the CLI.
- Chrome history extraction needs either root or a debuggable Chrome build.
- Media thumbnails are generated at full resolution; very large libraries may
  feel slow on first load.
- The AI assistant panel activates only when `PEGASUS__AI__API_KEY` is set.

---

**Authorized security testing only.** Use Pegasus on devices you own or have
written permission to assess.
