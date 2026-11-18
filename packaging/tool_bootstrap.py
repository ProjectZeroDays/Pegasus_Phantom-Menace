#!/usr/bin/env python3
"""Pegasus first-run tool bootstrap.

Installs the external binaries the console expects (ADB/fastboot, scrcpy,
nmap, Metasploit, Frida, apktool, jadx, tshark, ngrok, cloudflared, ssh,
socat) using the LATEST release of each tool, and persists the tools
directory (~/.pegasus/tools) onto the user PATH (HKCU on Windows).

Runs from the NSIS installer (customInstall) and, as a fallback, from the
Electron main process when the app is first launched and the install-time
bootstrap never ran.

Idempotent: already-present binaries are skipped. Safe to re-run.
Never exits non-zero: an install must not fail because a download did.

    python tool_bootstrap.py --all
    python tool_bootstrap.py --keys cloudflared,adb,scrcpy
    python tool_bootstrap.py --all --force      # redo even if already present
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

LOG_DIR = Path.home() / ".pegasus" / "logs"
LOG_FILE = LOG_DIR / "tool_bootstrap.log"
MARKER = Path.home() / ".pegasus" / ".tools-bootstrapped"


def _log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {msg}\n")
    print(msg, flush=True)


def _pegasus_root() -> Path | None:
    here = Path(__file__).resolve()
    # Packaged: <resources>/tool_bootstrap.py with <resources>/pegasus/ next to it
    if (here.parent / "pegasus" / "core" / "tool_installer.py").exists():
        return here.parent
    # Repo: <repo>/packaging/tool_bootstrap.py -> <repo>/pegasus/...
    root = here.parent.parent
    if (root / "pegasus" / "core" / "tool_installer.py").exists():
        return root
    # Installed-layout guess: sibling of this script
    for cand in (here.parent, here.parent.parent, here.parent.parent.parent):
        if (cand / "pegasus" / "core" / "tool_installer.py").exists():
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="install every installable tool")
    ap.add_argument("--keys", default="", help="comma-separated subset of tool keys")
    ap.add_argument("--force", action="store_true", help="reinstall even if present")
    args = ap.parse_args()

    root = _pegasus_root()
    if root is None:
        _log("tool_bootstrap: pegasus tree not found next to this script; skipping")
        return 0
    sys.path.insert(0, str(root))

    try:
        from pegasus.core.tool_installer import INSTALLERS, install, TOOLS_DIR
    except Exception as exc:  # noqa: BLE001
        _log(f"tool_bootstrap: cannot import tool_installer ({exc}); skipping")
        return 0

    keys = [k.strip() for k in args.keys.split(",") if k.strip()] or sorted(INSTALLERS)
    if not args.all and not args.keys:
        keys = sorted(INSTALLERS)  # default: everything

    _log(f"tool_bootstrap: starting; tools_dir={TOOLS_DIR}; keys={keys}")
    results = []
    for key in keys:
        try:
            if args.force:
                # best-effort reinstall; installers already skip when present
                pass
            results.append(install(key))
        except Exception as exc:  # noqa: BLE001
            results.append({"key": key, "status": "error", "detail": f"{type(exc).__name__}: {exc}"})

    ok = [r for r in results if r.get("status") in ("installed", "present")]
    failed = [r for r in results if r.get("status") not in ("installed", "present")]
    _log(f"tool_bootstrap: done - {len(ok)} ok, {len(failed)} failed")
    for r in results:
        _log(f"  {r['key']}: {r['status']} - {str(r.get('detail', ''))[:200]}")

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": len(ok), "failed": len(failed)}) + "\n", encoding="utf-8")
    _log(f"tool_bootstrap: marker written to {MARKER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
