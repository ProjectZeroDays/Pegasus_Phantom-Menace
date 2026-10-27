# Pegasus: Phantom Menace v2

**Android Device Management & Security Audit Platform — v2.0.0**

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey?style=for-the-badge)](https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace)
[![ADB](https://img.shields.io/badge/Requires-ADB-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://developer.android.com/tools/adb)
[![Metasploit](https://img.shields.io/badge/Metasploit-Integrated-red?style=for-the-badge)](https://metasploit.com)
[![Claude AI](https://img.shields.io/badge/Claude%20AI-Powered-purple?style=for-the-badge)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](./LICENSE)
[![Stars](https://img.shields.io/github/stars/ProjectZeroDays/Pegasus_Phantom-Menace?style=for-the-badge)](https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace/stargazers)

</div>

> **⚠️ For Educational & Personal Use Only**
> Use only on devices you own or have explicit written permission to access.

## Overview

Pegasus Phantom Menace v2 is a comprehensive Android device management and security audit platform built on a modular, plugin-based architecture. It integrates the best features from multiple security tools into a single, extensible framework:

- **CLI & TUI interfaces** with rich terminal UI
- **Web GUI** (Phase 3) for browser-based management
- **Plugin architecture** for easy extensibility
- **SQLite/PostgreSQL backend** for device, session, and finding storage
- **REST API** for remote management and automation

## Features by Module

### Device Management
- ADB USB/WiFi connection and management
- Device fingerprinting (model, Android version, patch level)
- Multi-device support with health checks
- File push/pull, shell execution, app management
- Keycode control, unlock/lock device

### Payload Generation
- msfvenom integration (5+ payload types)
- APK binding and obfuscation
- DNA tracking for payload attribution
- Mass payload generation with unique ports/encoders
- QR code payload delivery
- SSL pinning bypass (Frida scripts)

### Session Management
- Metasploit RPC integration
- Session keepalive and auto-fetch
- Device operations (shell, screenshot, logs, GPS, mic, camera)
- File upload/download
- Post-exploitation automation

### Security Audit
- CVE scanner (12+ built-in CVEs + NVD API)
- Vulnerability scanner (root detection, debuggable apps, permissions)
- APK static analysis (permissions, secrets, exported components)
- Exploit engine (activity launch, broadcast, content provider, deep link)
- SSL pinning bypass

### Intelligence & Reporting
- HTML/JSON report generation
- Campaign management
- Threat intelligence (CVE, IOC, VirusTotal, OTX)
- Chain of custody and audit logging
- AI-powered analysis (Claude integration)

### Network Tools
- nmap network scanning
- Port forwarding (socat, SSH -L/-R, iptables)
- ngrok tunnel management
- Listener monitoring

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace.git
cd Pegasus_Phantom-Menace/pegasus

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Initialize workspace and database
python -m pegasus.core.__main__ init

# Run Pegasus
python -m pegasus.core.__main__
```

### Or install as a package

```bash
pip install -e .
pegasus --help
```

## Usage

### CLI Mode

```bash
# List connected devices
pegasus run devices

# Get device information
pegasus run device-info <serial>

# Generate a payload
pegasus run payload-gen

# Scan for CVEs
pegasus run cve-scan

# Generate a report
pegasus run report-gen

# List all plugins
pegasus plugins

# Plugin info
pegasus plugin-info device
```

### Interactive Menu

```bash
pegasus menu
```

### Web GUI (Phase 3)

```bash
pegasus serve
```

## Architecture

```
pegasus/
├── core/              # Core framework (config, plugin, db, auth)
├── modules/           # Feature modules (device, payload, session, etc.)
├── ui/                # User interfaces (web, tui, cli)
├── plugins/           # External plugin system
├── data/              # CVE database, signatures, wordlists, templates
├── tests/             # Unit, integration, and e2e tests
├── scripts/           # Build, deploy, and dev scripts
└── docs/              # API docs, guides, architecture
```

### Plugin System

Pegasus uses a plugin-based architecture. Each module is a separate plugin that can be loaded, unloaded, or replaced independently:

```python
from pegasus.core.plugin import Plugin, PluginMetadata

class MyModule(Plugin):
    metadata = PluginMetadata(
        name="my_module",
        version="1.0.0",
        description="My custom module",
        author="Your Name",
        category="analysis",
        tags=["custom"],
    )
    
    async def initialize(self) -> bool:
        # Register commands, UI components, hooks
        return True
    
    async def shutdown(self) -> bool:
        return True
```

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
# Edit .env with your settings
```

Configuration uses nested environment variables with `__` as separator:

```
PEGASUS__AI__API_KEY=sk-ant-your-key
PEGASUS__METASPLOIT__RPC_PASSWORD=your_password
PEGASUS__SECURITY__JWT_SECRET=your-secret-key
```

## Requirements

### System Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.11+ | Runtime | `python3` |
| ADB | Device communication | `android-tools` |
| scrcpy | Screen mirroring | `scrcpy` |
| nmap | Network scanning | `nmap` |
| metasploit-framework | Payload generation & sessions | `metasploit-framework` |
| apktool | APK decompile/recompile | `apktool` |
| jadx | Java decompilation | `jadx` |
| frida | Runtime instrumentation | `frida-tools` |

### Python Dependencies

See `requirements.txt` for the full list.

## Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit

# Run with coverage
pytest --cov=pegasus --cov-report=html

# Run security scanning
bandit -r pegasus/
semgrep --config auto pegasus/
```

## Release

```bash
# Build executable
pyinstaller --onefile --noupx --name Pegasus-v2.0 --icon=assets/icon.ico pegasus/core/__main__.py

# Create release
git tag v2.0.0
git push origin v2.0.0
gh release create v2.0.0 --notes "Pegasus v2.0.0 release"
```

## Security & Disclaimer

**Pegasus is developed strictly for educational and authorized security testing purposes.**

- Only use on devices you own or have explicit written permission to test
- Unauthorized access to devices is illegal under CFAA, Computer Misuse Act, and equivalent laws
- The developers hold zero liability for misuse
- All data extraction features are intended for personal backup and security research

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m "feat: add your feature"`
4. Push to branch: `git push origin feature/your-feature`
5. Open a Pull Request

## License

MIT License — see [LICENSE](./LICENSE) for details.

## Support

- **Issues:** https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace/issues
- **Discussions:** https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace/discussions
- **Documentation:** https://pegasus-phantom-menace.readthedocs.io

---

Made with ❤️ by **ProjectZeroDays**
