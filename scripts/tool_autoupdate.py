#!/usr/bin/env python3
"""scripts/tool_autoupdate.py

Daily auto-update for all Pegasus-managed external tools.

Re-runs each tool's installer from pegasus.core.tool_installer to pick up the
latest version. Results are written to ~/.pegasus/tools/autoupdate.json so the
GUI can surface update status.

Safe to run from cron (Linux/macOS) or Task Scheduler (Windows) once per day.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running as `python scripts/tool_autoupdate.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pegasus.core.tool_installer import install, ensure_path, INSTALLERS  # noqa: E402
from pegasus.ui.web.backend.tools import TOOL_SPECS  # noqa: E402

STATE_FILE = Path.home() / ".pegasus" / "tools" / "autoupdate.json"


def run_update() -> dict:
    """Install/update every tool in TOOL_SPECS. Returns a summary dict."""
    ensure_path()
    results = []
    started = time.time()
    for spec in TOOL_SPECS:
        key = spec["key"]
        result = install(key)
        results.append(result)
    summary = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "duration_secs": round(time.time() - started, 2),
        "tools": len(results),
        "installed": sum(1 for r in results if r["status"] in ("installed", "present")),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    summary = run_update()
    print(f"[autoupdate] {summary['installed']}/{summary['tools']} tools present, "
          f"{summary['errors']} errors in {summary['duration_secs']}s")
    for r in summary["results"]:
        mark = "✓" if r["status"] in ("installed", "present") else "✗"
        print(f"  {mark} {r['key']}: {r['detail'][:80]}")
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
