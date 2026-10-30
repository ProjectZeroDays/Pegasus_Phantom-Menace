import re
from pathlib import Path

p = Path("CHANGELOG.md")
text = p.read_text(encoding="utf-8")

start = text.index("## [2.0.0]")
end = text.index("## [1.4.0]")

replacement = """## [2.0.0] — 2026-10-30

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

"""

p.write_text(text[:start] + replacement + text[end:], encoding="utf-8", newline="")
print("sections:", re.findall(r"^## \[[^\]]+\]", p.read_text(encoding="utf-8"), re.M))
