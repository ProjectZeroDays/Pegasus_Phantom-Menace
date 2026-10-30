# Pegasus Phantom Menace v2.1.0

Mission-control delivery release.

## Highlights

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
- **Quality** — 28 tests across auth, catalog, delivery and dashboard routes;
  ruff clean.

## Install

- `Pegasus-Web-v2.1.0.exe` — self-contained Windows console executable; run it,
  open `http://127.0.0.1:5000/`.
- `Pegasus-v2.1.0-Setup.exe` — NSIS installer with service or scheduled-task
  component and virtualenv bootstrap.
- `pegasus-source-v2.1.0.zip` — the full source tree.

First run redirects to `/setup`: create the operator account, set the USDC
wallet and passkey, then registration opens. Demo account: `demo` / `demo`.

## Notes

- Delivery intents populate the target composer; `auto_send` presses the send
  key after 1.6 s. Pickers that require a manual recipient tap still do.
- Bluetooth and NFC need the receiver in range.
- Shell collection depends on readable content providers; app data needs
  debuggable builds.

Authorized security testing only.
