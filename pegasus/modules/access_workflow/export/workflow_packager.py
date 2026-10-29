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

from rich.console import Console


class WorkflowExporter:
    """
    Exports workflows, skills, and custom commands for multiple agent frameworks.
    """

    def __init__(self, console: Console):
        self.console = console
        self.desktop = Path(os.path.expanduser("~/Desktop"))
        self.projects = Path("C:/Projects")
        self.timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def export_all(self) -> Dict[str, Path]:
        """Export all workflows to .zip on Desktop and install skills globally."""
        results = {}

        # 1. Create workflow export zip on Desktop
        zip_path = self._create_workflow_zip()
        results["workflow_zip"] = zip_path
        self.console.print(f"[green]✓ Workflow export zip: {zip_path}[/green]")

        # 2. Create skill files for each agent framework
        skill_paths = self._create_skill_files()
        results["skills"] = skill_paths
        for name, path in skill_paths.items():
            self.console.print(f"[green]✓ Skill installed: {name} -> {path}[/green]")

        # 3. Install skills globally
        self._install_skills_globally(skill_paths)
        self.console.print("[green]✓ Skills installed globally[/green]")

        # 4. Export to Desktop as well
        desktop_zip = self.desktop / f"pegasus_workflows_{self.timestamp}.zip"
        shutil.copy2(zip_path, desktop_zip)
        results["desktop_zip"] = desktop_zip
        self.console.print(f"[green]✓ Desktop export: {desktop_zip}[/green]")

        return results

    def _create_workflow_zip(self) -> Path:
        """Create a comprehensive workflow export zip."""
        zip_path = Path.home() / f"pegasus_workflows_{self.timestamp}.zip"

        # Collect all workflow-related files
        source_dirs = [
            Path("pegasus/modules/access_workflow"),
            Path("logs/access_workflow"),
            Path("pegasus/core/plugin"),
            Path("pegasus/core/config"),
        ]

        # Collect skill-related files
        skill_dirs = [
            Path(".openfable-skills"),
            Path(".mimocode-skills"),
            Path(".zcode-skills"),
            Path(".zfable-skills"),
            Path(".opencode-skills"),
        ]

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add workflow modules
            for src_dir in source_dirs:
                if src_dir.exists():
                    for f in src_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, f"workflows/{f.relative_to(src_dir.parent)}")

            # Add skill directories
            for src_dir in skill_dirs:
                if src_dir.exists():
                    for f in src_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, f"skills/{f.relative_to(src_dir.parent)}")

            # Add a manifest
            manifest = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "project": "Pegasus Phantom Menace v2.0",
                "version": "2.0.0",
                "frameworks": ["opencode", "openfable", "mimocode", "zfable", "zcode"],
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        return zip_path

    def _create_skill_files(self) -> Dict[str, Path]:
        """Create skill files for all agent frameworks."""
        skills = {}

        # OpenCode skill
        skills["opencode"] = self._write_opencode_skill()

        # OpenFable skill
        skills["openfable"] = self._write_openfable_skill()

        # Mimocode skill
        skills["mimocode"] = self._write_mimocode_skill()

        # Z-Fable skill (in C:\Projects\)
        skills["zfable"] = self._write_zfable_skill()

        # Z-Code skill
        skills["zcode"] = self._write_zcode_skill()

        return skills

    def _write_opencode_skill(self) -> Path:
        """Write OpenCode skill file."""
        skill_dir = Path(".opencode-skills")
        skill_dir.mkdir(exist_ok=True)

        skill = {
            "skill": "pegasus-access-workflow",
            "version": "2.0.0",
            "description": "Autonomous exploitation workflow engine for Pegasus Phantom Menace",
            "author": "ProjectZeroDays",
            "category": "security",
            "entry_point": ".opencode-skills/pegasus-access-workflow.json",
            "commands": 22,
            "installation": "skill install .opencode-skills/pegasus-access-workflow.json",
        }

        skill_file = skill_dir / "pegasus-access-workflow.json"
        skill_file.write_text(json.dumps(skill, indent=2))

        # Create the actual skill definition
        skill_def = {
            "name": "pegasus-access-workflow",
            "version": "2.0.0",
            "triggers": [
                "/access-workflow-run",
                "/access-workflow-history",
                "/access-workflow-rates",
                "/access-workflow-category",
                "/access-menu",
                "/access-manual",
                "/access-autonomous",
                "/access-vectors",
                "/access-zero-click",
                "/access-post-exploit",
                "/post-exploit-menu",
                "/post-exploit-fingerprint",
                "/post-exploit-persistence",
                "/post-exploit-credentials",
                "/post-exploit-lateral",
                "/post-exploit-exfiltrate",
                "/post-exploit-chain",
            ],
            "execution": {
                "command": "python -m pegasus.core <command>",
                "cwd": "<project_root>",
            },
            "workflows": [
                "full_lifecycle",
                "stage_by_stage",
            ],
            "vectors": [
                "adb", "fastboot", "qr_pairing", "usb", "bluetooth", "nfc",
                "sms", "whatsapp", "telegram", "signal", "discord", "slack",
                "messenger", "email", "wifi", "mitm", "zero_click", "zero_day",
            ],
        }

        skill_def_file = skill_dir / "pegasus-access-workflow-def.json"
        skill_def_file.write_text(json.dumps(skill_def, indent=2))

        return skill_file

    def _write_openfable_skill(self) -> Path:
        """Write OpenFable skill file."""
        skill_dir = Path(".openfable-skills")
        skill_dir.mkdir(exist_ok=True)

        skill = {
            "skill": "pegasus-access-workflow",
            "version": "2.0.0",
            "description": "Autonomous exploitation workflow engine for OpenFable coding agent",
            "author": "ProjectZeroDays",
            "category": "security",
            "entry_point": ".openfable-skills/pegasus-access-workflow.json",
            "commands": 22,
            "installation": "skill install .openfable-skills/pegasus-access-workflow.json",
        }

        skill_file = skill_dir / "pegasus-access-workflow.json"
        skill_file.write_text(json.dumps(skill, indent=2))

        return skill_file

    def _write_mimocode_skill(self) -> Path:
        """Write Mimocode skill file."""
        skill_dir = Path(".mimocode-skills")
        skill_dir.mkdir(exist_ok=True)

        skill = {
            "skill": "pegasus-access-workflow",
            "version": "2.0.0",
            "description": "Autonomous exploitation workflow engine for Mimocode",
            "author": "ProjectZeroDays",
            "category": "security",
            "entry_point": ".mimocode-skills/pegasus-access-workflow.json",
            "commands": 22,
            "installation": "skill install .mimocode-skills/pegasus-access-workflow.json",
        }

        skill_file = skill_dir / "pegasus-access-workflow.json"
        skill_file.write_text(json.dumps(skill, indent=2))

        return skill_file

    def _write_zfable_skill(self) -> Path:
        """Write Z-Fable skill file (in C:\\Projects\\)."""
        skill_dir = self.projects / ".zfable-skills"
        skill_dir.mkdir(exist_ok=True)

        skill = {
            "skill": "pegasus-access-workflow",
            "version": "2.0.0",
            "description": "Autonomous exploitation workflow engine for Z-Fable",
            "author": "ProjectZeroDays",
            "category": "security",
            "entry_point": ".zfable-skills/pegasus-access-workflow.json",
            "commands": 22,
            "installation": "skill install .zfable-skills/pegasus-access-workflow.json",
        }

        skill_file = skill_dir / "pegasus-access-workflow.json"
        skill_file.write_text(json.dumps(skill, indent=2))

        return skill_file

    def _write_zcode_skill(self) -> Path:
        """Write Z-Code skill file."""
        skill_dir = Path(".zcode-skills")
        skill_dir.mkdir(exist_ok=True)

        skill = {
            "skill": "pegasus-access-workflow",
            "version": "2.0.0",
            "description": "Autonomous exploitation workflow engine for Z-Code",
            "author": "ProjectZeroDays",
            "category": "security",
            "entry_point": ".zcode-skills/pegasus-access-workflow.json",
            "commands": 22,
            "installation": "skill install .zcode-skills/pegasus-access-workflow.json",
        }

        skill_file = skill_dir / "pegasus-access-workflow.json"
        skill_file.write_text(json.dumps(skill, indent=2))

        return skill_file

    def _install_skills_globally(self, skill_paths: Dict[str, Path]):
        """Install skills globally for all agent frameworks."""
        # Install to OpenCode global skills directory
        opencode_skills = Path.home() / ".config" / "opencode" / "skills"
        opencode_skills.mkdir(parents=True, exist_ok=True)

        # Copy all skill files to global OpenCode skills directory
        for name, path in skill_paths.items():
            if path.exists():
                dest = opencode_skills / f"pegasus-{name}"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(path.parent, dest)

        # Also copy to OpenFable global
        openfable_skills = Path.home() / ".config" / "opencode" / "skills"
        for name, path in skill_paths.items():
            if path.exists():
                dest = openfable_skills / f"pegasus-{name}"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(path.parent, dest)


# Module entry point
def create_exporter(console: Console) -> WorkflowExporter:
    return WorkflowExporter(console)
