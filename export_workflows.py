"""
Pegasus Phantom Menace v2 - Workflow Export & Skill Packager

Exports all workflows into a .zip on Desktop and converts them into
usable skills/custom commands for:
- Mimocode
- Opencode
- OpenFable
- Z-Fable (in C:/Projects/)
- Z-Code
- Opencode locally

Installs them globally for use everywhere.
"""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class WorkflowExporter:
    """Exports workflows, skills, and custom commands for multiple agent frameworks."""

    def __init__(self, console=None):
        self.console = console
        self.desktop = Path(os.path.expanduser("~/Desktop"))
        self.projects = Path("C:/Projects")
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def export_all(self) -> Dict[str, Path]:
        """Export all workflows to .zip on Desktop and install skills globally."""
        results = {}

        # 1. Create workflow export zip
        zip_path = self._create_workflow_zip()
        results["workflow_zip"] = zip_path
        if self.console:
            self.console.print(f"[green]OK Workflow export zip: {zip_path}[/green]")
        else:
            print(f"OK Workflow export zip: {zip_path}")

        # 2. Copy to Desktop
        desktop_zip = self.desktop / f"pegasus_workflows_{self.timestamp}.zip"
        shutil.copy2(zip_path, desktop_zip)
        results["desktop_zip"] = desktop_zip
        if self.console:
            self.console.print(f"[green]OK Desktop export: {desktop_zip}[/green]")
        else:
            print(f"OK Desktop export: {desktop_zip}")

        # 3. Install skills globally to OpenCode
        opencode_skills = Path.home() / ".config" / "opencode" / "skills"
        opencode_skills.mkdir(parents=True, exist_ok=True)

        skill_dirs = {
            "opencode": Path(".opencode-skills"),
            "openfable": Path(".openfable-skills"),
            "mimocode": Path(".mimocode-skills"),
            "zfable": Path("C:/Projects/.zfable-skills"),
            "zcode": Path(".zcode-skills"),
        }

        for name, path in skill_dirs.items():
            if path.exists():
                dest = opencode_skills / f"pegasus-{name}"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(path, dest)
                results[name] = dest
                if self.console:
                    self.console.print(f"[green]OK Skill installed globally: {name} -> {dest}[/green]")
                else:
                    print(f"OK Skill installed globally: {name} -> {dest}")

        return results

    def _create_workflow_zip(self) -> Path:
        """Create a comprehensive workflow export zip."""
        zip_path = Path.home() / f"pegasus_workflows_{self.timestamp}.zip"

        source_dirs = [
            Path("pegasus/modules/access_workflow"),
        ]

        skill_dirs = [
            Path(".opencode-skills"),
            Path(".mimocode-skills"),
            Path(".zcode-skills"),
            Path(".zfable-skills"),
            Path(".opencode-skills"),
        ]

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for src_dir in source_dirs:
                if src_dir.exists():
                    for f in src_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, f"workflows/{f.relative_to(src_dir.parent)}")

            for src_dir in skill_dirs:
                if src_dir.exists():
                    for f in src_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, f"skills/{f.relative_to(src_dir.parent)}")

            manifest = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "project": "Pegasus Phantom Menace v2.0",
                "version": "2.0.0",
                "frameworks": ["opencode", "openfable", "mimocode", "zfable", "zcode"],
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        return zip_path


if __name__ == "__main__":
    exporter = WorkflowExporter()
    results = exporter.export_all()
    print("\nExport complete!")
    for name, path in results.items():
        print(f"  {name}: {path}")