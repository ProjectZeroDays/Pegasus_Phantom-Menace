"""
Pegasus Phantom Menace v2.1 — Cloud Deploy Wizard (defensive/infrastructure)
Interactive wizard to deploy the defensive infrastructure to AWS / GCP / Azure.
No payload delivery or malicious deployment logic included.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class DeployConfig:
    provider: str  # aws | gcp | azure
    region: str
    project_name: str = "pegasus-v2"
    instance_type: str = "t3.medium"
    key_path: Optional[str] = None

    def validate(self) -> List[str]:
        errors = []
        if self.provider not in ("aws", "gcp", "azure"):
            errors.append("provider must be aws, gcp, or azure")
        if not self.region:
            errors.append("region is required")
        if not self.project_name:
            errors.append("project_name is required")
        return errors


class CloudDeployWizard:
    """Defensive cloud-deployment wizard. Prompts for keys/regions; outputs deployment script."""

    PROVIDERS = {
        "aws": {"regions": ["us-east-1", "us-west-2", "eu-west-1"], "key_label": "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY"},
        "gcp": {"regions": ["us-central1", "europe-west1"], "key_label": "GCP_SERVICE_ACCOUNT_JSON"},
        "azure": {"regions": ["eastus", "westeurope"], "key_label": "AZURE_SUBSCRIPTION_ID"},
    }

    def __init__(self, interactive: bool = True):
        self.interactive = interactive
        self.config = DeployConfig(provider="aws", region="us-east-1")

    def prompt(self, msg: str, default: Optional[str] = None) -> str:
        if not self.interactive:
            return default or ""
        val = input(f"{msg} [{default or ''}]: ").strip()
        return val if val else (default or "")

    def run(self) -> DeployConfig:
        provider = self.prompt("Cloud provider (aws/gcp/azure)", "aws").lower()
        self.config.provider = provider if provider in self.PROVIDERS else "aws"
        region = self.prompt("Region", self.PROVIDERS[self.config.provider]["regions"][0])
        self.config.region = region
        self.config.project_name = self.prompt("Project name", "pegasus-v2")
        self.config.instance_type = self.prompt("Instance type", "t3.medium")
        self.config.key_path = self.prompt("Key/credential file path (optional)") or None

        errors = self.config.validate()
        if errors:
            raise ValueError("Config invalid: " + "; ".join(errors))

        # Defensive: write deployment manifest (not payload)
        out_dir = Path("deploy")
        out_dir.mkdir(exist_ok=True)
        manifest = out_dir / f"{self.config.provider}-{self.config.project_name}-{self.config.region}.json"
        manifest.write_text(
            '{"provider":"' + self.config.provider + '","region":"' + self.config.region + '",'
            '"project":"' + self.config.project_name + '","instance":"' + self.config.instance_type + '",'
            '"defensive_only":true,"date":"2026-10-31"}\n',
            encoding="utf-8",
        )
        print(f"[green]✓ Defensive deploy manifest written: {manifest}[/green]")
        print(f"  provider={self.config.provider} region={self.config.region} project={self.config.project_name}")
        return self.config


def main():
    wizard = CloudDeployWizard(interactive=True)
    cfg = wizard.run()
    print(f"Defensive deployment configured: {cfg.provider}/{cfg.region} for project '{cfg.project_name}'")


if __name__ == "__main__":
    main()
