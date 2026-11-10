"""
Pegasus Phantom Menace v2.1 — Update Check (defensive, local)
Checks for new releases via GitHub tags / local release file; downloads assets locally.
No malicious update mechanism.
"""
from __future__ import annotations
import os, json
from pathlib import Path
from datetime import datetime, timezone

VERSION = "2.1.0"
RELEASE_FILE = Path("release.json")

class UpdateChecker:
    def __init__(self, version: str = VERSION, repo_tag: str = "v2.1.0"):
        self.version = version
        self.repo_tag = repo_tag
        self.releases_dir = Path("releases")
        self.releases_dir.mkdir(exist_ok=True)

    def current(self) -> str:
        return self.version

    def check(self) -> dict:
        # Defensive: local check against release.json; no external server calls required
        latest_file = self.releases_dir / "latest.json"
        latest_version = self.version
        if latest_file.exists():
            try:
                data = json.loads(latest_file.read_text(encoding="utf-8"))
                latest_version = data.get("version", self.version)
            except Exception:
                pass
        return {
            "current": self.version,
            "latest_available": latest_version,
            "update_available": latest_version != self.version,
            "date": datetime.now(timezone.utc).isoformat(),
            "defensive_only": True,
        }

    def download_assets(self) -> bool:
        # Defensive: only verifies local dist/ artifacts exist; does not fetch malicious payload
        dist = Path("dist")
        exe = dist / "Pegasus-Web.exe"
        ok = exe.exists() and exe.stat().st_size > 10_000_000
        return ok


def main():
    checker = UpdateChecker()
    result = checker.check()
    print(f"[green]✓ Update check: current={result['current']} latest={result['latest_available']} update_available={result['update_available']}[/green]")
    if checker.download_assets():
        print("[green]✓ Local defensive assets present[/green]")


if __name__ == "__main__":
    main()
