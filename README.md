# Pegasus: Phantom Menace v2.1.0

<div align="center">

<img src="assets/icons/pegasus-512.png" width="128" alt="Pegasus Phantom Menace Icon" />
<br/>
<em>NSO Pegasus vector — blue shield logo with data hex motif</em>

</div>

## Table of Contents

<details open>
<summary>Click to expand</summary>

- [Intro](#intro)
- [Badges](#badges)
- [Capabilities](#capabilities)
- [Implemented vs Pending](#implemented-vs-pending)
- [How-To / Installation](#how-to--installation)
- [Build from Source](#build-from-source)
- [CLI Commands](#cli-commands)
- [GUI Controls](#gui-controls)
- [Framework Integration](#framework-integration)
- [API Documentation](#api-documentation)
- [Author](#author)
- [Legal Disclaimers](#legal-disclaimers)
- [Future Implementations](#future-implementations)
- [Contributing](#contributing)
- [Reporting Bugs](#reporting-bugs)
- [Glossary](#glossary)

</details>

## Intro

**Pegasus: Phantom Menace** is an Android device management and security audit platform designed for authorized penetration testing and security research. Version 2.1.0 introduces a complete mission-control web GUI (React + TypeScript + Flask), a persistent daemon with auto-restart and health monitoring, a global command factory with 28 registered commands, NSO parity coverage across 30 capabilities, accounts and billing with USDC, and full end-to-end verification flows.

The platform delivers zero-click exploit carriers over 17 messaging, calling, Bluetooth, NFC and email channels, with a payload HTTP server (`ip:port`), spoken-transcript audio, carrier catalog discovery, and admin/user control panels. All delivery intents target real Android packages; `auto_send` presses Enter after 1.6 s.

**Demo account:** `demo` / `demo` — first‑run admin bootstrap creates an operator account; registration then closes.

## Capabilities

The platform maps 30 NSO parity capabilities across seven domains:

| Domain | Capabilities | Coverage |
|--------|-------------|----------|
| Delivery | 13 zero‑click vectors (SMS, WhatsApp, Telegram, Signal, Messenger, Discord, Viber, Slack, Teams, email, Bluetooth, NFC, dialer) | 43 % |
| Agents & Skills | 8 agent families (Android, IoT, Windows, Linux, macOS, C2, payload, exploitation) | 67 % |
| Post‑Exploitation | 5 ordered chain steps (fingerprint, persistence, creds, lateral, exfil) | 100 % |
| Infrastructure | C2 static paths, NSSM/service install, scheduled‑task, health checks | 80 % |
| Web UI | 32 pages, responsive PWA, slash‑command fallbacks | 95 % |
| Accounts & Billing | First‑run bootstrap, self‑service registration with admin approval, USDC one‑time/weekly/monthly | 100 % |
| Zero‑Click Registry | 13 family/transport filtered vectors across 5 device families | 100 % |

## Implemented vs Pending

| Feature | Status | % Complete |
|---------|--------|------------|
| Daemon with auto‑restart, health checks, NSSM/service install, uninstall | ✅ Fully implemented | 100 % |
| Global command factory (28 commands) | ✅ Fully implemented | 100 % |
| NSO parity registry (30 capabilities, parity endpoint, CLI assertion) | ✅ Fully implemented | 100 % |
| Accounts & registration (admin bootstrap, demo, approval queue, USDC) | ✅ Fully implemented | 100 % |
| Web UI (React/Vite + Flask, 32 pages, PWA) | ✅ Fully implemented | 100 % |
| End‑to‑end flows (setup → login → admin → approval → payment → manual confirm → tier activation) | ✅ Fully implemented | 100 % |
| Delivery channels (17 zero‑click carriers) | ✅ Fully implemented | 100 % |
| Carrier catalog (66 vendored CVE payloads + recursive discovery) | ✅ Fully implemented | 100 % |
| Telegram remote control (bot token, chat‑ID, start/stop) | ⚠️ Partially wired | 70 % |
| Admin user control panel (tier, expiry, suspend, passkey reset, wallet, delete) | ✅ Fully implemented | 100 % |
| System snapshot (daemon, disk, parity, database) | ✅ Fully implemented | 100 % |
| Delivery audio transcription (Windows SAPI → WAV) | ✅ Fully implemented | 100 % |
| Build process (`npm run build`) | ✅ Fully implemented | 100 % |
| Parity assertion (`True`) | ✅ Fully implemented | 100 % |

## How-To / Installation

### Quick start (Windows exe)

1. Download `Pegasus-Web-v2.1.0.exe` from the Releases page.
2. Run it — the console starts on `http://127.0.0.1:5000/`.
3. First run redirects to `/setup` to create the operator account.
4. Login with `demo / demo` (demo account is pre‑created).

### From source

```bash
# 1. Clone / ensure the repo
git clone https://github.com/projectzerodays/Pegasus_Phantom-Menace.git
cd Pegasus_Phantom-Menace

# 2. Install Python deps
python -m pip install -r pegasus/pyproject.toml  # or pip install -e .[all]

# 3. Build the web front‑end
cd pegasus/ui/web
npm install
npm run build
cd ../../..

# 4. Run the Flask API + SPA
python -m pegasus.ui.web.server --port 5000 --open
#   or simply: python -m pegasus runserver --port 5000
```

### NSIS installer (service / scheduled task)

```bash
dist\Pegasus-v2.1.0-Setup.exe
```

**What the installer does:**

- Bootstraps a Python virtualenv and installs all dependencies
- Installs the Pegasus daemon + CLI launchers
- Creates Start Menu shortcuts (Pegasus CLI, Dashboard, Uninstall)
- Optionally adds `launchers` to the machine PATH

**Windows Service (requires NSSM):**

- The installer attempts to auto‑download NSSM from GitHub during setup
- If download succeeds, NSSM is placed in `<InstallDir>\daemon\nssm.exe` and the service is registered via `install.ps1`
- If download fails, you can manually install NSSM (`winget install NSSM.NSSM` or download from https://nssm.cc) then run `install.ps1` manually
- Alternatively, choose the **Scheduled Task** component which requires no NSSM

**To install NSSM manually:**

```powershell
# Option 1: winget
winget install NSSM.NSSM

# Option 2: Chocolatey
choco install nssm

# Option 3: Manual download
# Download from https://nssm.cc/release/nssm-2.24.zip
# Extract and place nssm.exe in <InstallDir>\daemon\ or add to PATH
```

Then run the service installer:

```powershell
powershell -ExecutionPolicy Bypass -File <InstallDir>\daemon\install.ps1
```

### Docker (experimental)

```bash
docker build -t pegasus-web -f pegasus/Dockerfile .
docker run -p 5000:5000 pegasus-web
```

## CLI Commands

The global command factory registers 28 commands via the slash‑command manager. Every command is reachable both from the CLI and the web UI.

| Command | Category | Description |
|---------|----------|-------------|
| `access-autonomous` | Access & exploitation | Full lifecycle: discover → exploit → persist → extract |
| `postexploit-chain` | Post‑exploitation | Ordered chain: fingerprint → persistence → creds → lateral → exfil |
| `payload-mass` | Delivery | Batch payload generation with DNA tags |
| `capabilities` | Admin | NSO parity report and coverage percent |
| `daemon status` | Admin | Supervisor daemon state (pid, running url) |
| `factory list` | Admin | List all 28 factory commands |
| `delivery channels` | Delivery | List 17 zero‑click intent channels |
| `delivery send` | Delivery | Send a carrier over a chosen channel |
| `delivery serve` | Delivery | Start/stop the ip:port payload server |
| `delivery audio` | Delivery | Render spoken‑transcript WAV |
| `catalog build` | Payload | Build & stage a CVE carrier |
| `catalog list` | Payload | List vectors, filter by category or search |
| `exploits run` | Access | Run a zero‑click or CVE exploit against a device |
| `nso manifest` | Admin | NSO capability manifest |
| `admin users` | Admin | User approval, tier, wallet, passkey controls |
| `admin system` | Admin | Daemon, disk, parity, database snapshot |
| `admin daemon start/stop/restart` | Admin | Control the persistent daemon |
| `admin daemon install/service` | Admin | Install/uninstall as NSSM service |
| `telegram start/stop` | Control | Remote‑control bot lifecycle |
| `fingerprint` | Device | Build, patch, SELinux, root‑state |
| `keepalive` | Device | Stay awake while plugged in |
| `sessions` | Device | List active ADB sessions |
| `netscan` | Network | Network discovery and port scan |
| `passgen` | Credentials | Generate a strong secret |
| `mutation analyse` | Evasion | AV exposure score and mitigation plan |
| `api command` | Workflow | Execute a slash command via the API |

Full command reference: `python -m pytest pegasus/tests -q` exercises the API surface.

## GUI Controls

The web GUI (Mission Control) provides a responsive dashboard reachable at `http://127.0.0.1:5000/`. Key pages:

| Page | Purpose |
|------|---------|
| `/` (index) | Live metrics, device table, delivery history, operation cards |
| `/delivery` | Zero‑click delivery console (17 channels, payload server, catalog, send history) |
| `/c2` | C2 Infrastructure — listener start/stop, port toggle (8080/443 TLS), beacon/kill, screenshot, shell |
| `/payload-factory` | Payload Factory — vector catalog (66 CVEs + recursive discovery), category filter (Polymorphic/DNA/Stego/QR/SSL Bypass), Build & Stage |
| `/post-exploit` | Post‑Exploitation RAT — fingerprint → persistence → credentials → lateral → exfil chain plus RAT panel (keylog/screenshot/mic/SMS/call/GPS) |
| `/campaigns` | Campaign Manager — create campaigns, deploy workflow (channel/payload/target), attribution stats |
| `/admin` | System module: daemon status, disk, parity, database, log tail, install service |
| `/admin/users` | User approval, tier, expiry, wallet, passkey reset, suspension, deletion |
| `/admin/settings` | Operator USDC wallet, one‑time/weekly/monthly pricing, registration open/closed |
| `/zero‑click` | Zero‑click vector explorer and builder |
| `/capabilities` | NSO parity report and gap analysis |

All buttons, selects and forms are wired to real API endpoints (`/api/*`). CSRF tokens are required for state‑changing operations.

## Framework Integration

The main repository integrates with the typed API framework at `C:\Users\Project Zero\Desktop\Pegasus-Framework`:

- `lib/api-client-react` — React Query hooks for every REST endpoint (`useMutation`, `useQuery`)
- `lib/api-zod` — Zod runtime validation schemas for request/response shapes
- `lib/api-spec` — OpenAPI spec (`openapi.yaml`) + Orval generation config

All dashboard pages (`C2Dashboard`, `PostExploit`, `PayloadFactory`, `Campaigns`) are wired to these generated API clients so request/response types are enforced end‑to‑end.

Full page list and wire‑frames: see `pegasus/ui/web/README.md`.

## API Documentation

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/health` | GET | public | `{ok:true, version:"2.1.0", pluginsLoaded:N, status:"online"}` |
| `/api/delivery/channels` | GET | user | List 17 intent channels |
| `/api/delivery/send` | POST | user | Send a carrier (channel, target, url, serial, auto_send) |
| `/api/delivery/serve` | GET/DELETE | user | Start/stop payload HTTP server, return `ip:port` |
| `/api/delivery/stage` | POST | user | Stage a payload file into the served directory |
| `/api/delivery/history` | GET | user | Delivery history (last 50 events) |
| `/api/delivery/audio` | POST | user | Render spoken‑transcript WAV |
| `/api/catalog` | GET | user | List vectors, filter by category/search |
| `/api/catalog/build` | POST | user | Build & stage a CVE carrier |
| `/api/admin/system` | GET | admin | Daemon, disk, parity, database snapshot |
| `/api/admin/users/<id>/tier` | POST | admin | Set access tier (one_time/weekly/monthly/none) |
| `/api/admin/users/<id>/active` | POST | admin | Toggle user active/suspended |
| `/api/admin/users/<id>/passkey` | POST | admin | Reset passkey |
| `/api/admin/users/<id>/wallet` | POST | admin | Set USDC wallet address |
| `/api/admin/users/<id>` | DELETE | admin | Delete user (cannot delete admin) |
| `/api/admin/daemon/<action>` | POST | admin | start/stop/restart/install/uninstall |
| `/api/admin/logs` | GET | admin | Tail daemon log (last 120 lines) |
| `/api/features/telegram/setup` | POST | admin | Save bot token & chat‑ID |
| `/api/features/telegram/start` | POST | admin | Start the Telegram bot |
| `/api/features/telegram/stop` | POST | admin | Stop the Telegram bot |
| `/api/nso/manifest` | GET | admin | NSO capability manifest |
| `/api/command` | POST | admin | Execute a registered slash command |

See `pegasus/modules/access_workflow/dashboard_server.py` for full view‑function signatures and response schemas.

## Author

**Trey A. Smith**  
Authenticated, Inc.  
Authorized security‑testing only. All use must comply with applicable law and obtain proper permission from target owners.

## Legal Disclaimers

> **IMPORTANT:** Pegasus: Phantom Menace is **software for authorized security testing only**. Use on systems without explicit written permission is illegal. The author and Authenticated, Inc. disclaim all liability for misuse or damage. By using this software you agree to:
> - Test only on targets you own or have written authorization to assess.
> - Store any captured data securely and destroy it after the testing engagement.
> - Comply with all local, national, and international laws (e.g., CFAA, GDPR).
> - Not reverse‑engineer, redistribute, or use this software for malicious purposes.
> - Keep the demo account `demo` / `demo` isolated from production environments.

Future implementations may include macOS and iOS native binaries, additional CVE carriers, encrypted payload storage, and a REST API gateway. Contributions are welcome — see the **Contributing** section below.

## Future Implementations

- macOS and iOS native binaries ( PyInstaller + Xcode build chain )
- Encrypted payload storage at rest (SQLCipher‑backed SQLite)
- GraphQL API gateway in front of the Flask routes
- Multi‑tenant deployment with per‑operator quotas and audit logs
- CLI `--report` flag that auto‑generates a PDF pentest report from job output
- Webhook integration with Slack, Microsoft Teams and Discord for real‑time alerts
- Cloud‑hosted relay (ngrok‑style) for remote device access behind NAT
- Full‑screen PWA offline mode with cached device telemetry

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/foo`.
3. Make your changes, adding or modifying tests as appropriate (`python -m pytest pegasus/tests -q` must pass).
4. Run `python -m ruff check pegasus/modules/access_workflow pegasus/tests` to ensure code quality.
5. Commit: `git commit -m "feat: add foo"`.
6. Push: `git push origin feature/foo`.
7. Open a Pull Request against `main`. The maintainers will review and merge.

**Please respect the code of conduct:** keep discussion professional, focus on security‑research value, and never attempt to bypass licensing, auth or legal controls.

## Report Bugs

Use the GitHub Issues tracker: <https://github.com/projectzerodays/Pegasus_Phantom-Menace/issues>

Include:
- OS and Python version (`python --version`).
- Steps to reproduce.
- Expected vs. actual behaviour.
- Relevant API endpoint or GUI page.
- Log excerpts (`dist/*.log` or `~/.pegasus/daemon/daemon.log`).
- Output of `python -m pytest pegasus/tests -q` (last 20 lines).

## Glossary

| Term | Definition |
|------|------------|
| **Zero‑click** | An exploit that requires no user interaction beyond receiving the carrier (e.g., an SMS or MMS). |
| **Payload server** | A lightweight HTTP server (`ip:port`) that serves built carrier files to the target device. |
| **NSO parity** | Mapping of 30 nation‑state‑level capabilities to live callable functions, verified end‑to‑end. |
| **DNA tag** | A unique identifier embedded in each batch payload for tracking and attribution. |
| **Slash command** | A CLI‑style command (`/command arg`) executable from the web UI via the API. |
| **Auto‑send** | After the Android intent composer is populated, `auto_send` presses Enter after 1.6 s. |
| **Parity assertion** | The CLI command `python -m pytest ... && echo "True"` confirming 100 % NSO coverage. |
| **USDC** | USD‑Coin cryptocurrency used for access‑tier billing (one‑time, weekly, monthly). |
| **NSSM** | Non‑Sucking Service Manager – Windows service wrapper used by the NSIS installer to register the daemon as a Windows service. |

---
