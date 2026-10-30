# Pegasus Phantom Menace v2.1.0

Mission-control delivery release — accounts, daemon, 17-channel delivery, the
full 33-page web console, and 100%-mapped NSO-class capability parity.

## Highlights

- **Web console, productionised** — 33 pages served by `pegasus serve` from a
  single process, packaged as `Pegasus-Web-v2.1.0.exe`. Every action runs as a
  background job with live output, progress and cancellation. ADB telemetry
  (contacts, SMS, calls, Chrome history, apps, media, Wi-Fi, GPS, keystrokes,
  usage) is cached locally with geofences, keyword tracking and device notes.
  See [`pegasus/ui/web/README.md`](pegasus/ui/web/README.md) and
  [`docs/WEB_GUI_ARCHITECTURE.md`](docs/WEB_GUI_ARCHITECTURE.md).
- **Zero-click delivery console** — 17 channels: SMS, WhatsApp (text and voice
  note), Telegram, Signal, Facebook Messenger (text and voice note), Discord,
  Viber, Slack, Teams, Google Messages, email with prefilled subject, Bluetooth,
  NFC, dialer and the generic share sheet.
- **Payload server** — one click starts an ip:port HTTP server on the LAN,
  stages builds and fills the URL automatically.
- **Spoken transcripts** — audio channels synthesise a WAV with Windows SAPI,
  spelling the URL in words, push it to the device and attach it as `audio/*`.
- **Carrier catalog** — 66 vendored CVE payload generators plus discovery across
  `C:/Projects`, with category filters, search and build-and-stage.
- **New landing page** — blue mission-control layout with live device metrics,
  device actions, carrier catalog, delivery history and 15 wired operation
  cards.
- **Admin modules** — user control (tier, expiry, suspend, passkey reset,
  wallet, delete), system snapshot (daemon, disk, parity, database) and log tail.
- **Brand** — base64 Pegasus shield in the sidebar, README header and the app
  icon set (ICO, ICNS, PNG, PWA manifest).
- **Quality** — 30 web-console tests plus the auth, catalog, delivery and
  dashboard suites; ruff clean; strict TypeScript.

## Fixed in this release

- **All 14 plugins load.** Module metadata is now bound to the class before
  instantiation; previously 10 modules failed with `type object 'X' has no
  attribute 'metadata'`. Commands went 16 → 40.
- Frozen bundles load plugins by direct import when no `plugin.py` exists on
  disk.
- Job output no longer duplicates lines or truncates table cells, and keeps
  Unicode borders on Windows.
- Invalid TOML in `pyproject.toml` that broke pytest and ruff.
- Windows launcher no longer crashes on arrow glyphs.

## Install

- `Pegasus-Web-v2.1.0.zip` — self-contained Windows console executable; unzip,
  run `Pegasus-Web.exe`, open `http://127.0.0.1:5000/`.
- `Pegasus-v2.1.0-Setup.exe` — NSIS installer with service or scheduled-task
  component and virtualenv bootstrap.
- `pegasus-source-v2.1.0.zip` — the full source tree.

First run redirects to `/setup`: create the operator account, set the USDC
wallet and passkey, then registration opens. Demo account: `demo` / `demo`.

## Verify

```bash
python -m pytest pegasus/ui/web/tests -q      # 30 passed
cd pegasus/ui/web && npm run typecheck        # clean
```

Manual smoke test: the footer should read **14 plugins · 40 commands**; run a
command card and watch the terminal stream.

## Notes

- Delivery intents populate the target composer; `auto_send` presses the send
  key after 1.6 s. Pickers that require a manual recipient tap still do.
- Bluetooth and NFC need the receiver in range.
- Shell collection depends on readable content providers; app data needs
  debuggable builds.
- Interactive module prompts are answered from queued values in the web
  console; heavy free-text flows are best driven from the CLI.

Authorized security testing only.
