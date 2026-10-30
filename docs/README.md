# Pegasus Phantom Menace v2 — Documentation

| Document | Contents |
|---|---|
| [`../README.md`](../README.md) | Project overview, feature matrix, build instructions |
| [`../CHANGELOG.md`](../CHANGELOG.md) | Version history with every fix and addition |
| [`../RELEASE_NOTES_v2.0.0.md`](../RELEASE_NOTES_v2.0.0.md) | v2.0.0 release summary and upgrade steps |
| [`WEB_GUI_ARCHITECTURE.md`](WEB_GUI_ARCHITECTURE.md) | Layer diagram, plugin loading, job pipeline, telemetry, packaging decisions |
| [`../pegasus/README.md`](../pegasus/README.md) | Python package guide: modules, plugin contract, configuration |
| [`../pegasus/ui/web/README.md`](../pegasus/ui/web/README.md) | Web GUI: quick start, full page map, complete API reference, testing |
| [`../pegasus-mobile/README.md`](../pegasus-mobile/README.md) | Native Android companion app |

---

## At a glance

**Pegasus Phantom Menace** is an Android device management and security audit
platform. It combines a plugin-based Python engine (14 modules, 40 commands),
three interfaces (web GUI, TUI menu, Click CLI), and a native Android companion.

### Interfaces

| Interface | Entry point | Notes |
|---|---|---|
| Web GUI | `pegasus serve` · `python -m pegasus.ui.web.server` · `Pegasus-Web.exe` | 32 pages, live jobs, ADB telemetry |
| Interactive menu | `pegasus menu` | Rich TUI, grouped commands |
| CLI | `pegasus run <command>` | Scriptable, same command registry |
| Slash commands | `pegasus slash <name>` | High-level flows (46 commands) |
| Legacy C2 dashboard | `pegasus dashboard` | Template dashboard on port 5050 |
| Android app | `pegasus-mobile/` | Kotlin WebView shell with bottom nav |

### Capability map

| Domain | Modules | Highlights |
|---|---|---|
| Access | `access_workflow`, `post_exploitation` | ADB/fastboot/QR/USB, zero-click families, 12-stage lifecycle, 6-stage post-exploitation |
| Device | `device`, `brutdroid` | Fingerprinting, shell, emulator rooting, Frida, Burp cert |
| Assessment | `cve_scanner`, `analysis` | 12 built-in CVEs, NVD lookup, patch-level scoring |
| Payloads | `payload`, `passgen` | msfvenom, APK binding, DNA tracking, QR delivery, wordlists |
| Sessions | `session` | Metasploit RPC, keepalive, auto-fetch |
| Reporting | `reporting` | HTML/JSON reports, campaign grouping |
| Network | `network` | nmap, port forwarding, ngrok, listeners |
| Integrations | `integrations` | 46 slash commands bridging high-level flows |

---

## First run

```bash
git clone https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace.git
cd Pegasus_Phantom-Menace

python -m venv venv
venv\Scripts\activate            # Windows
pip install -r pegasus/requirements.txt

python -m pegasus.core.__main__ init     # create workspace + database
python -m pegasus.ui.web.server --open   # launch the GUI
```

The workspace defaults to `~/.pegasus` and holds the database, logs, reports,
payloads and the telemetry store.

---

## Configuration

Environment variables use `__` to nest (`PEGASUS__SECTION__KEY`):

```
PEGASUS__AI__API_KEY=sk-ant-...          # enables the AI assistant
PEGASUS__AI__MODEL=claude-sonnet-4-6
PEGASUS__METASPLOIT__RPC_HOST=127.0.0.1
PEGASUS__METASPLOIT__RPC_PORT=55553
PEGASUS__METASPLOIT__RPC_PASSWORD=...
PEGASUS__DATABASE__TYPE=sqlite           # or postgresql
PEGASUS__SECURITY__JWT_SECRET=...
```

The GUI's Settings page lists these with copy buttons and live values.

---

## Verification

```bash
python -m pytest pegasus/ui/web/tests -q     # 24 GUI backend tests
cd pegasus/ui/web && npm run typecheck       # strict TypeScript
pegasus plugins                              # expect 14 plugins
pegasus run cve-list                         # expect 12 CVEs
```

---

## Disclaimer

Authorized security testing only. Use Pegasus on devices you own or have
explicit written permission to assess. The authors accept no liability for
misuse.
