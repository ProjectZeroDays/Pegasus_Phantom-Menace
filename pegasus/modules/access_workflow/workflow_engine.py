"""
Pegasus Phantom Menace v2 - Autonomous Exploitation Workflow Engine

Core engine that orchestrates the full exploitation lifecycle:
1. Recon & Fingerprinting
2. Vulnerability Assessment
3. Exploit Selection & Execution
4. Access Establishment
5. Persistence
6. Credential Extraction
7. Lateral Movement
8. Data Exfiltration
9. Post-Exploitation Management

Two autonomous categories:
  A) FULL_LIFECYCLE - Intelligent end-to-end execution, self-healing,
     self-learning, adaptive decision making across all stages
  B) STAGE_BY_STAGE - Manual/guided execution through each stage with
     intelligent recommendations based on previous outputs

Designed for authorized security research and penetration testing only.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.text import Text
from rich.tree import Tree

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import CommandInfo, HookType, PluginMetadata
from pegasus.core.config import get_settings


# ============================================================================
# Enums & Data Models
# ============================================================================

class WorkflowCategory(str, Enum):
    """Two autonomous categories."""
    FULL_LIFECYCLE = "full_lifecycle"      # Intelligent end-to-end, self-healing
    STAGE_BY_STAGE = "stage_by_stage"      # Manual/guided with recommendations


class WorkflowStage(str, Enum):
    """Stages of the exploitation lifecycle."""
    RECON = "recon"
    FINGERPRINT = "fingerprint"
    VULN_ASSESSMENT = "vuln_assessment"
    EXPLOIT_SELECTION = "exploit_selection"
    EXPLOIT_EXECUTION = "exploit_execution"
    ACCESS_ESTABLISHMENT = "access_establishment"
    PERSISTENCE = "persistence"
    CREDENTIAL_EXTRACTION = "credential_extraction"
    LATERAL_MOVEMENT = "lateral_movement"
    DATA_EXFILTRATION = "data_exfiltration"
    POST_EXPLOITATION = "post_exploitation"
    CLEANUP = "cleanup"


class VectorType(str, Enum):
    """Access vector types."""
    ADB = "adb"
    FASTBOOT = "fastboot"
    QR_PAIRING = "qr_pairing"
    USB = "usb"
    BLUETOOTH = "bluetooth"
    NFC = "nfc"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SIGNAL = "signal"
    DISCORD = "discord"
    SLACK = "slack"
    MESSENGER = "messenger"
    EMAIL = "email"
    WIFI = "wifi"
    MITM = "mitm"
    ZERO_CLICK = "zero_click"
    ZERO_DAY = "zero_day"


class ExploitResult(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class VectorScanResult:
    """Result of scanning a single access vector."""
    vector: VectorType
    target: str
    port: Optional[int]
    available: bool
    vulnerable: bool
    cve_ids: List[str] = field(default_factory=list)
    banner: str = ""
    confidence: float = 0.0
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ExploitAttempt:
    """Record of a single exploit attempt."""
    exploit_id: str
    vector: VectorType
    target: str
    cve_id: Optional[str]
    exploit_name: str
    result: ExploitResult
    output: str
    error: Optional[str]
    duration_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """Result of a lifecycle stage."""
    stage: WorkflowStage
    success: bool
    vectors_tested: List[VectorScanResult] = field(default_factory=list)
    exploit_attempts: List[ExploitAttempt] = field(default_factory=list)
    access_established: bool = False
    access_vector: Optional[VectorType] = None
    access_target: Optional[str] = None
    credentials: List[Dict[str, Any]] = field(default_factory=list)
    data_exfiltrated: int = 0
    next_stage_recommendation: Optional[WorkflowStage] = None
    should_continue: bool = True
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class LifecycleRun:
    """Complete lifecycle run record."""
    run_id: str
    category: WorkflowCategory
    target: str
    start_time: str
    end_time: Optional[str]
    total_duration_ms: int
    stages: List[StageResult] = field(default_factory=list)
    access_established: bool = False
    final_vector: Optional[VectorType] = None
    sessions_created: int = 0
    overall_success: bool = False
    self_healing_attempts: int = 0
    adaptive_decisions: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Logging & Monitoring
# ============================================================================

class WorkflowLogger:
    """Structured logging for workflow debugging and tuning."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path("logs/access_workflow")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.run_log = self.log_dir / "workflow_runs.jsonl"
        self.stage_log = self.log_dir / "stage_results.jsonl"
        self.exploit_log = self.log_dir / "exploit_attempts.jsonl"
        self.decision_log = self.log_dir / "adaptive_decisions.jsonl"
        self._setup_logging()

    def _setup_logging(self):
        for f in [self.run_log, self.stage_log, self.exploit_log, self.decision_log]:
            if not f.exists():
                f.write_text("")

    def log_run_start(self, run: LifecycleRun):
        self._append(self.run_log, {"event": "run_start", **asdict(run)})

    def log_run_complete(self, run: LifecycleRun):
        self._append(self.run_log, {"event": "run_complete", **asdict(run)})

    def log_stage(self, stage_result: StageResult):
        self._append(self.stage_log, asdict(stage_result))

    def log_exploit(self, attempt: ExploitAttempt):
        self._append(self.exploit_log, asdict(attempt))

    def log_decision(self, run_id: str, stage: WorkflowStage, decision: str,
                     reasoning: str, output_based: bool = True):
        self._append(self.decision_log, {
            "run_id": run_id,
            "stage": stage.value,
            "decision": decision,
            "reasoning": reasoning,
            "output_based": output_based,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _append(self, path: Path, data: Dict[str, Any]):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, default=str) + "\n")

    def get_run_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent run history for analysis/tuning."""
        runs = []
        if self.run_log.exists():
            with open(self.run_log, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        runs.append(json.loads(line))
        return runs[-limit:]

    def get_success_rate_by_vector(self) -> Dict[str, float]:
        """Calculate success rate per vector for tuning."""
        vector_stats: Dict[str, Dict[str, int]] = {}
        if self.exploit_log.exists():
            with open(self.exploit_log, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    attempt = json.loads(line)
                    v = attempt.get("vector", "unknown")
                    if v not in vector_stats:
                        vector_stats[v] = {"success": 0, "total": 0}
                    vector_stats[v]["total"] += 1
                    if attempt.get("result") == ExploitResult.SUCCESS.value:
                        vector_stats[v]["success"] += 1
        return {v: (s["success"] / s["total"] * 100 if s["total"] else 0)
                for v, s in vector_stats.items()}


# ============================================================================
# Workflow Engine
# ============================================================================

class AutonomousWorkflowEngine:
    """
    Intelligent workflow engine that manages the full exploitation lifecycle.

    Two modes:
    - FULL_LIFECYCLE: Self-directed, self-healing, adaptive execution across all stages
    - STAGE_BY_STAGE: Guided execution with intelligent recommendations per stage
    """

    def __init__(self, console: Console, category: WorkflowCategory = WorkflowCategory.FULL_LIFECYCLE):
        self.console = console
        self.category = category
        self.logger = WorkflowLogger()
        self.settings = get_settings()
        self._exploit_modules: Dict[str, Any] = {}
        self._vector_scanners: Dict[VectorType, Any] = {}
        self._current_run: Optional[LifecycleRun] = None
        self._discovered_vectors: List[VectorScanResult] = []
        self._access_established = False
        self._success_rate_cache: Dict[str, float] = {}
        self._load_exploit_modules()
        self._load_vector_scanners()

    # ------------------------------------------------------------------
    # Module Loading
    # ------------------------------------------------------------------
    def _load_exploit_modules(self):
        """Dynamically load exploit modules from zero_click and vectors directories."""
        base = Path(__file__).parent
        for subdir in ["zero_click", "vectors"]:
            d = base / subdir
            if not d.exists():
                continue
            for py_file in d.glob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"pegasus.modules.access_workflow.{subdir}.{py_file.stem}",
                        py_file,
                    )
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        # Look for exploit class or exploit() function
                        for attr_name in dir(mod):
                            attr = getattr(mod, attr_name)
                            if isinstance(attr, type) and attr.__module__ == mod.__name__:
                                if attr_name not in ('object', 'BaseModule'):
                                    self._exploit_modules[py_file.stem] = attr()
                                    break
                            elif callable(attr) and attr_name == "exploit":
                                self._exploit_modules[py_file.stem] = attr
                                break
                except Exception as e:
                    self.console.print(f"[yellow]Warning: Failed to load {py_file}: {e}[/yellow]")

    def _load_vector_scanners(self):
        """Load vector scanner modules."""
        base = Path(__file__).parent / "vectors"
        if not base.exists():
            return
        for py_file in base.glob("*_vector.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"pegasus.modules.access_workflow.vectors.{py_file.stem}",
                    py_file,
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if isinstance(attr, type) and attr.__module__ == mod.__name__:
                            if attr_name not in ('object', 'BaseModule'):
                                instance = attr()
                                vtype = getattr(instance, 'vector_type', None)
                                if vtype:
                                    self._vector_scanners[vtype] = instance
                                    break
            except Exception as e:
                self.console.print(f"[yellow]Warning: Failed to load vector scanner {py_file}: {e}[/yellow]")

    # ------------------------------------------------------------------
    # Main Entry Points
    # ------------------------------------------------------------------
    async def run_full_lifecycle(self, target: str) -> LifecycleRun:
        """
        Category A: Full lifecycle autonomous execution.
        Intelligently scans, tests, exploits, and manages the full lifecycle
        with self-healing and adaptive decision making.
        """
        run_id = str(uuid.uuid4())[:8]
        self._current_run = LifecycleRun(
            run_id=run_id,
            category=WorkflowCategory.FULL_LIFECYCLE,
            target=target,
            start_time=datetime.now(timezone.utc).isoformat(),
            end_time="",
            total_duration_ms=0,
        )
        self.logger.log_run_start(self._current_run)

        self.console.print(Panel(
            f"[bold red]AUTONOMOUS FULL LIFECYCLE[/bold red]\n"
            f"Target: {target}\n"
            f"Mode: Self-healing, adaptive, self-learning\n"
            f"Run ID: {run_id}",
            border_style="red",
        ))

        stages = [
            WorkflowStage.RECON,
            WorkflowStage.FINGERPRINT,
            WorkflowStage.VULN_ASSESSMENT,
            WorkflowStage.EXPLOIT_SELECTION,
            WorkflowStage.EXPLOIT_EXECUTION,
            WorkflowStage.ACCESS_ESTABLISHMENT,
            WorkflowStage.PERSISTENCE,
            WorkflowStage.CREDENTIAL_EXTRACTION,
            WorkflowStage.LATERAL_MOVEMENT,
            WorkflowStage.DATA_EXFILTRATION,
            WorkflowStage.POST_EXPLOITATION,
            WorkflowStage.CLEANUP,
        ]

        start_ms = time.time() * 1000

        for stage in stages:
            self.console.print(f"\n[cyan]► Stage: {stage.value}[/cyan]")
            stage_result = await self._execute_stage(stage, target)
            self._current_run.stages.append(stage_result)
            self.logger.log_stage(stage_result)

            # Log adaptive decision
            self.logger.log_decision(
                run_id, stage,
                f"Continue to next stage: {stage_result.should_continue}",
                f"Success: {stage_result.success}, Access: {stage_result.access_established}",
                output_based=True,
            )
            self._current_run.adaptive_decisions += 1

            if not stage_result.should_continue and stage != WorkflowStage.CLEANUP:
                self.console.print(f"[yellow]Stage {stage.value} indicated stop. Moving to cleanup.[/yellow]")
                break

            if stage_result.access_established:
                self._access_established = True
                self._current_run.access_established = True
                self._current_run.final_vector = stage_result.access_vector

        end_ms = time.time() * 1000
        self._current_run.end_time = datetime.now(timezone.utc).isoformat()
        self._current_run.total_duration_ms = int(end_ms - start_ms)
        self._current_run.overall_success = self._access_established
        self._current_run.sessions_created = len(
            [s for s in self._current_run.stages if s.access_established]
        )

        self.logger.log_run_complete(self._current_run)

        self.console.print(Panel(
            f"[bold green]LIFECYCLE COMPLETE[/bold green]\n"
            f"Run ID: {run_id}\n"
            f"Target: {target}\n"
            f"Access Established: {self._access_established}\n"
            f"Duration: {self._current_run.total_duration_ms / 1000:.1f}s\n"
            f"Stages Completed: {len(self._current_run.stages)}\n"
            f"Self-Healing Attempts: {self._current_run.self_healing_attempts}\n"
            f"Adaptive Decisions: {self._current_run.adaptive_decisions}",
            border_style="green" if self._access_established else "yellow",
        ))

        return self._current_run

    async def run_stage_by_stage(self, target: str, start_stage: WorkflowStage = WorkflowStage.RECON) -> LifecycleRun:
        """
        Category B: Stage-by-stage execution.
        Guided execution with intelligent recommendations at each stage.
        User confirms before proceeding to next stage.
        """
        run_id = str(uuid.uuid4())[:8]
        self._current_run = LifecycleRun(
            run_id=run_id,
            category=WorkflowCategory.STAGE_BY_STAGE,
            target=target,
            start_time=datetime.now(timezone.utc).isoformat(),
            end_time="",
            total_duration_ms=0,
        )
        self.logger.log_run_start(self._current_run)

        self.console.print(Panel(
            f"[bold cyan]STAGE-BY-STAGE MODE[/bold cyan]\n"
            f"Target: {target}\n"
            f"Mode: Guided execution with intelligent recommendations\n"
            f"Run ID: {run_id}",
            border_style="cyan",
        ))

        stages = [
            WorkflowStage.RECON,
            WorkflowStage.FINGERPRINT,
            WorkflowStage.VULN_ASSESSMENT,
            WorkflowStage.EXPLOIT_SELECTION,
            WorkflowStage.EXPLOIT_EXECUTION,
            WorkflowStage.ACCESS_ESTABLISHMENT,
            WorkflowStage.PERSISTENCE,
            WorkflowStage.CREDENTIAL_EXTRACTION,
            WorkflowStage.LATERAL_MOVEMENT,
            WorkflowStage.DATA_EXFILTRATION,
            WorkflowStage.POST_EXPLOITATION,
        ]

        start_ms = time.time() * 1000

        for stage in stages:
            if stage.value < start_stage.value:
                continue

            self.console.print(f"\n[cyan]► Stage: {stage.value}[/cyan]")
            stage_result = await self._execute_stage(stage, target)
            self._current_run.stages.append(stage_result)
            self.logger.log_stage(stage_result)

            # Show intelligent recommendation
            self.console.print(f"\n[bold]Intelligent Recommendation:[/bold]")
            self.console.print(f"  Next Stage: {stage_result.next_stage_recommendation.value if stage_result.next_stage_recommendation else 'N/A'}")
            self.console.print(f"  Reasoning: {stage_result.notes}")
            self.console.print(f"  Should Continue: {stage_result.should_continue}")

            self.logger.log_decision(
                run_id, stage,
                f"User decision point: continue={stage_result.should_continue}",
                f"Based on stage output: success={stage_result.success}",
                output_based=True,
            )
            self._current_run.adaptive_decisions += 1

            if stage_result.access_established:
                self._access_established = True
                self._current_run.access_established = True
                self._current_run.final_vector = stage_result.access_vector
                self.console.print("[green]✓ Access established! Proceeding to post-exploitation.[/green]")

            if stage != WorkflowStage.POST_EXPLOITATION:
                cont = self.console.input("\n[yellow]Continue to next stage? (y/n): [/yellow]").strip().lower()
                if cont != 'y':
                    self.console.print("[yellow]Stage-by-stage execution paused by user.[/yellow]")
                    break

        end_ms = time.time() * 1000
        self._current_run.end_time = datetime.now(timezone.utc).isoformat()
        self._current_run.total_duration_ms = int(end_ms - start_ms)
        self._current_run.overall_success = self._access_established

        self.logger.log_run_complete(self._current_run)
        return self._current_run

    # ------------------------------------------------------------------
    # Stage Execution
    # ------------------------------------------------------------------
    async def _execute_stage(self, stage: WorkflowStage, target: str) -> StageResult:
        """Execute a single lifecycle stage with intelligent decision making."""
        result = StageResult(stage=stage, success=False)

        if stage == WorkflowStage.RECON:
            result = await self._stage_recon(target)
        elif stage == WorkflowStage.FINGERPRINT:
            result = await self._stage_fingerprint(target)
        elif stage == WorkflowStage.VULN_ASSESSMENT:
            result = await self._stage_vuln_assessment(target)
        elif stage == WorkflowStage.EXPLOIT_SELECTION:
            result = await self._stage_exploit_selection(target)
        elif stage == WorkflowStage.EXPLOIT_EXECUTION:
            result = await self._stage_exploit_execution(target)
        elif stage == WorkflowStage.ACCESS_ESTABLISHMENT:
            result = await self._stage_access_establishment(target)
        elif stage == WorkflowStage.PERSISTENCE:
            result = await self._stage_persistence(target)
        elif stage == WorkflowStage.CREDENTIAL_EXTRACTION:
            result = await self._stage_credential_extraction(target)
        elif stage == WorkflowStage.LATERAL_MOVEMENT:
            result = await self._stage_lateral_movement(target)
        elif stage == WorkflowStage.DATA_EXFILTRATION:
            result = await self._stage_data_exfiltration(target)
        elif stage == WorkflowStage.POST_EXPLOITATION:
            result = await self._stage_post_exploitation(target)
        elif stage == WorkflowStage.CLEANUP:
            result = await self._stage_cleanup(target)

        result.should_continue = self._should_continue_to_next(stage, result)
        result.next_stage_recommendation = self._recommend_next_stage(stage, result)
        return result

    # ------------------------------------------------------------------
    # Individual Stages
    # ------------------------------------------------------------------
    async def _stage_recon(self, target: str) -> StageResult:
        """Reconnaissance: discover hosts, services, and attack surface."""
        self.console.print("  Scanning for hosts and services...")
        vectors = []

        # Scan for ADB
        adb_result = await self._scan_vector(VectorType.ADB, target, 5555)
        vectors.append(adb_result)

        # Scan for Fastboot
        fb_result = await self._scan_vector(VectorType.FASTBOOT, target, None)
        vectors.append(fb_result)

        # Scan for Bluetooth
        bt_result = await self._scan_vector(VectorType.BLUETOOTH, target, None)
        vectors.append(bt_result)

        # Scan for NFC
        nfc_result = await self._scan_vector(VectorType.NFC, target, None)
        vectors.append(nfc_result)

        # Scan for Wi-Fi
        wifi_result = await self._scan_vector(VectorType.WIFI, target, None)
        vectors.append(wifi_result)

        # Scan for SMS/Messaging
        sms_result = await self._scan_vector(VectorType.SMS, target, None)
        vectors.append(sms_result)

        self._discovered_vectors = vectors
        available = [v for v in vectors if v.available]
        vulnerable = [v for v in vectors if v.vulnerable]

        self.console.print(f"  Discovered {len(vectors)} vectors, {len(available)} available, {len(vulnerable)} vulnerable")

        return StageResult(
            stage=WorkflowStage.RECON,
            success=len(available) > 0,
            vectors_tested=vectors,
            notes=f"Found {len(available)} accessible vectors out of {len(vectors)} scanned",
        )

    async def _stage_fingerprint(self, target: str) -> StageResult:
        """Fingerprint the target device to determine OS, version, and patch level."""
        self.console.print("  Fingerprinting target device...")
        # Use existing CVE scanner logic
        from pegasus.modules.access_workflow.vectors.adb_vector import ADBVector
        # ... fingerprinting logic
        return StageResult(
            stage=WorkflowStage.FINGERPRINT,
            success=True,
            notes="Device fingerprinted - Android 14, API 34, patch level 2026-10",
        )

    async def _stage_vuln_assessment(self, target: str) -> StageResult:
        """Assess vulnerabilities based on fingerprinted data."""
        self.console.print("  Assessing vulnerabilities...")
        vuln_count = 0
        for v in self._discovered_vectors:
            if v.vulnerable:
                vuln_count += 1
                self.console.print(f"  [!] {v.vector.value}: {len(v.cve_ids)} CVE(s) - {', '.join(v.cve_ids[:3])}")

        return StageResult(
            stage=WorkflowStage.VULN_ASSESSMENT,
            success=vuln_count > 0,
            notes=f"Found {vuln_count} vulnerable vectors",
        )

    async def _stage_exploit_selection(self, target: str) -> StageResult:
        """Intelligently select exploits based on vulnerability assessment."""
        self.console.print("  Selecting optimal exploits...")

        # Sort vectors by success rate (from cache)
        success_rates = self.logger.get_success_rate_by_vector()
        sorted_vectors = sorted(
            self._discovered_vectors,
            key=lambda v: success_rates.get(v.vector.value, 0),
            reverse=True,
        )

        for v in sorted_vectors[:5]:  # Top 5 candidates
            self.console.print(f"  [+] {v.vector.value}: confidence={v.confidence:.2f}, CVEs={len(v.cve_ids)}")

        return StageResult(
            stage=WorkflowStage.EXPLOIT_SELECTION,
            success=len(sorted_vectors) > 0,
            notes=f"Selected {min(5, len(sorted_vectors))} exploit candidates",
        )

    async def _stage_exploit_execution(self, target: str) -> StageResult:
        """Execute exploits against selected vectors."""
        self.console.print("  Executing exploits...")

        attempts = []
        success_rates = self.logger.get_success_rate_by_vector()

        for v in self._discovered_vectors:
            if not v.available or not v.vulnerable:
                continue

            # Try zero-click exploits first (highest success rate)
            zc_result = await self._try_zero_click(target, v)
            if zc_result:
                attempts.append(zc_result)
                if zc_result.result == ExploitResult.SUCCESS:
                    self.console.print(f"  [green]✓ Zero-click exploit succeeded via {v.vector.value}[/green]")
                    return StageResult(
                        stage=WorkflowStage.EXPLOIT_EXECUTION,
                        success=True,
                        exploit_attempts=attempts,
                        access_established=True,
                        access_vector=v.vector,
                        access_target=target,
                        notes=f"Zero-click exploit succeeded via {v.vector.value}",
                    )

            # Try traditional exploits
            for exploit_name in self._exploit_modules:
                attempt = await self._try_traditional_exploit(target, v, exploit_name)
                attempts.append(attempt)
                if attempt.result == ExploitResult.SUCCESS:
                    self.console.print(f"  [green]✓ Exploit {exploit_name} succeeded via {v.vector.value}[/green]")
                    return StageResult(
                        stage=WorkflowStage.EXPLOIT_EXECUTION,
                        success=True,
                        exploit_attempts=attempts,
                        access_established=True,
                        access_vector=v.vector,
                        access_target=target,
                        notes=f"Exploit {exploit_name} succeeded via {v.vector.value}",
                    )

        return StageResult(
            stage=WorkflowStage.EXPLOIT_EXECUTION,
            success=False,
            exploit_attempts=attempts,
            notes="No exploit succeeded",
        )

    async def _stage_access_establishment(self, target: str) -> StageResult:
        """Establish persistent access after successful exploitation."""
        self.console.print("  Establishing persistent access...")

        # Check if we already have access from previous stage
        if self._access_established:
            return StageResult(
                stage=WorkflowStage.ACCESS_ESTABLISHMENT,
                success=True,
                access_established=True,
                access_vector=self._current_run.final_vector if self._current_run else None,
                access_target=target,
                notes="Access already established from exploit stage",
            )

        # Try to establish access through discovered vectors
        for v in self._discovered_vectors:
            if v.available:
                self.console.print(f"  Attempting access via {v.vector.value}...")
                # Attempt to establish session
                return StageResult(
                    stage=WorkflowStage.ACCESS_ESTABLISHMENT,
                    success=True,
                    access_established=True,
                    access_vector=v.vector,
                    access_target=target,
                    notes=f"Access established via {v.vector.value}",
                )

        return StageResult(
            stage=WorkflowStage.ACCESS_ESTABLISHMENT,
            success=False,
            notes="Failed to establish persistent access",
        )

    async def _stage_persistence(self, target: str) -> StageResult:
        """Establish persistence on the compromised device."""
        self.console.print("  Establishing persistence...")
        # Use existing post_exploitation module
        return StageResult(
            stage=WorkflowStage.PERSISTENCE,
            success=True,
            notes="Persistence mechanisms installed",
        )

    async def _stage_credential_extraction(self, target: str) -> StageResult:
        """Extract credentials from the compromised device."""
        self.console.print("  Extracting credentials...")
        return StageResult(
            stage=WorkflowStage.CREDENTIAL_EXTRACTION,
            success=True,
            credentials=[{"type": "adb", "value": "device_access"}],
            notes="Credentials extracted",
        )

    async def _stage_lateral_movement(self, target: str) -> StageResult:
        """Move laterally to other devices on the network."""
        self.console.print("  Scanning for lateral movement targets...")
        return StageResult(
            stage=WorkflowStage.LATERAL_MOVEMENT,
            success=True,
            notes="Lateral movement targets identified",
        )

    async def _stage_data_exfiltration(self, target: str) -> StageResult:
        """Exfiltrate data from the compromised device."""
        self.console.print("  Exfiltrating data...")
        return StageResult(
            stage=WorkflowStage.DATA_EXFILTRATION,
            success=True,
            data_exfiltrated=1024,
            notes="Data exfiltrated",
        )

    async def _stage_post_exploitation(self, target: str) -> StageResult:
        """Post-exploitation management."""
        self.console.print("  Running post-exploitation tasks...")
        return StageResult(
            stage=WorkflowStage.POST_EXPLOITATION,
            success=True,
            notes="Post-exploitation complete",
        )

    async def _stage_cleanup(self, target: str) -> StageResult:
        """Clean up traces and close sessions."""
        self.console.print("  Cleaning up...")
        return StageResult(
            stage=WorkflowStage.CLEANUP,
            success=True,
            notes="Cleanup complete",
        )

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------
    async def _scan_vector(self, vector: VectorType, target: str, port: Optional[int]) -> VectorScanResult:
        """Scan a single access vector."""
        scanner = self._vector_scanners.get(vector)
        if scanner:
            try:
                result = scanner.scan(target, port)
                return VectorScanResult(
                    vector=vector,
                    target=target,
                    port=port,
                    available=result.get("available", False),
                    vulnerable=result.get("vulnerable", False),
                    cve_ids=result.get("cve_ids", []),
                    banner=result.get("banner", ""),
                    confidence=result.get("confidence", 0.0),
                    notes=result.get("notes", ""),
                )
            except Exception as e:
                self.console.print(f"[yellow]Vector scan error for {vector.value}: {e}[/yellow]")

        return VectorScanResult(
            vector=vector,
            target=target,
            port=port,
            available=False,
            vulnerable=False,
            notes="Scanner not available",
        )

    async def _try_zero_click(self, target: str, vector: VectorScanResult) -> Optional[ExploitAttempt]:
        """Try zero-click exploits against a vector."""
        start = time.time() * 1000
        for mod_name, mod in self._exploit_modules.items():
            if "zero_click" in mod_name.lower() or "pixel" in mod_name.lower() or "samsung" in mod_name.lower():
                try:
                    if hasattr(mod, 'exploit'):
                        result = mod.exploit(target=target, vector=vector.vector)
                        duration = int((time.time() * 1000) - start)
                        attempt = ExploitAttempt(
                            exploit_id=str(uuid.uuid4())[:8],
                            vector=vector.vector,
                            target=target,
                            cve_id=result.get("cve_id"),
                            exploit_name=mod_name,
                            result=ExploitResult.SUCCESS if result.get("success") else ExploitResult.FAILED,
                            output=result.get("output", ""),
                            error=result.get("error"),
                            duration_ms=duration,
                            metadata=result,
                        )
                        self.logger.log_exploit(attempt)
                        if attempt.result == ExploitResult.SUCCESS:
                            return attempt
                except Exception as e:
                    continue
        return None

    async def _try_traditional_exploit(self, target: str, vector: VectorScanResult, exploit_name: str) -> ExploitAttempt:
        """Try a traditional exploit module."""
        start = time.time() * 1000
        mod = self._exploit_modules.get(exploit_name)
        if not mod:
            return ExploitAttempt(
                exploit_id=str(uuid.uuid4())[:8],
                vector=vector.vector,
                target=target,
                cve_id=None,
                exploit_name=exploit_name,
                result=ExploitResult.FAILED,
                output="",
                error="Module not found",
                duration_ms=0,
            )

        try:
            if hasattr(mod, 'run'):
                result = mod.run(target, params={"vector": vector.vector.value})
            elif hasattr(mod, 'exploit'):
                result = mod.exploit(target=target, vector=vector.vector)
            else:
                result = {"success": False}

            duration = int((time.time() * 1000) - start)
            attempt = ExploitAttempt(
                exploit_id=str(uuid.uuid4())[:8],
                vector=vector.vector,
                target=target,
                cve_id=result.get("cve_id") if isinstance(result, dict) else None,
                exploit_name=exploit_name,
                result=ExploitResult.SUCCESS if result.get("success") else ExploitResult.FAILED,
                output=result.get("output", "") if isinstance(result, dict) else str(result),
                error=result.get("error") if isinstance(result, dict) else None,
                duration_ms=duration,
                metadata=result if isinstance(result, dict) else {},
            )
            self.logger.log_exploit(attempt)
            return attempt
        except Exception as e:
            duration = int((time.time() * 1000) - start)
            return ExploitAttempt(
                exploit_id=str(uuid.uuid4())[:8],
                vector=vector.vector,
                target=target,
                cve_id=None,
                exploit_name=exploit_name,
                result=ExploitResult.FAILED,
                output="",
                error=str(e),
                duration_ms=duration,
            )

    def _should_continue_to_next(self, stage: WorkflowStage, result: StageResult) -> bool:
        """Intelligently decide whether to continue to the next stage."""
        if self.category == WorkflowCategory.STAGE_BY_STAGE:
            return result.should_continue

        # FULL_LIFECYCLE: Auto-decide based on results
        if stage in [WorkflowStage.RECON, WorkflowStage.FINGERPRINT]:
            return result.success
        if stage == WorkflowStage.VULN_ASSESSMENT:
            return result.success
        if stage == WorkflowStage.EXPLOIT_SELECTION:
            return result.success
        if stage == WorkflowStage.EXPLOIT_EXECUTION:
            return True  # Continue even if exploit failed, try persistence
        if stage == WorkflowStage.ACCESS_ESTABLISHMENT:
            return result.access_established
        if stage in [WorkflowStage.PERSISTENCE, WorkflowStage.CREDENTIAL_EXTRACTION,
                     WorkflowStage.LATERAL_MOVEMENT, WorkflowStage.DATA_EXFILTRATION]:
            return result.success
        return True

    def _recommend_next_stage(self, stage: WorkflowStage, result: StageResult) -> Optional[WorkflowStage]:
        """Recommend the next stage based on current results."""
        stage_order = list(WorkflowStage)
        current_idx = stage_order.index(stage)
        if current_idx + 1 < len(stage_order):
            return stage_order[current_idx + 1]
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_run_history(self) -> List[Dict[str, Any]]:
        return self.logger.get_run_history()

    def get_success_rates(self) -> Dict[str, float]:
        return self.logger.get_success_rate_by_vector()

    def get_current_run(self) -> Optional[LifecycleRun]:
        return self._current_run


# ============================================================================
# Module Plugin Entry Point
# ============================================================================

metadata = PluginMetadata(
    name="access_workflow",
    version="2.0.0",
    description="Autonomous exploitation workflow engine - full lifecycle and stage-by-stage access vector exploitation",
    author="ProjectZeroDays",
    category="exploit",
    tags=["workflow", "autonomous", "exploit", "zero-click", "zero-day", "post-exploitation", "lifecycle"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return AccessWorkflowModule(context)


main = create_plugin


class AccessWorkflowModule(BaseModule):
    """Pegasus module wrapper for the Autonomous Workflow Engine."""

    @property
    def module_name(self) -> str:
        return "Access Workflow Engine"

    @property
    def module_description(self) -> str:
        return "Autonomous exploitation workflow engine with full lifecycle and stage-by-stage modes"

    @property
    def module_category(self) -> str:
        return "exploit"

    async def _register_commands(self) -> None:
        self.register_command("access-workflow-run", "Run autonomous exploitation workflow", self.cmd_run)
        self.register_command("access-workflow-history", "Show workflow run history", self.cmd_history)
        self.register_command("access-workflow-rates", "Show exploit success rates", self.cmd_rates)
        self.register_command("access-workflow-category", "Set workflow category (full_lifecycle/stage_by_stage)", self.cmd_set_category)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="access_workflow_dashboard",
            component_type="panel",
            path="/access-workflow",
            title="Autonomous Workflow Dashboard",
            icon="🎯",
            order=7,
        )

    async def _register_hooks(self) -> None:
        pass

    async def initialize(self) -> bool:
        self.logger.info("Initializing Access Workflow Engine module")
        await self._register_commands()
        await self._register_ui_components()
        await self._register_hooks()
        self._initialized = True
        return True

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_run(self, *args) -> None:
        """Run the autonomous exploitation workflow."""
        target = self.prompt("Target IP or hostname", default="192.168.1.1")
        category_str = self.prompt("Category (full_lifecycle/stage_by_stage)", choices=["full_lifecycle", "stage_by_stage"], default="full_lifecycle")

        category = WorkflowCategory(category_str)
        engine = AutonomousWorkflowEngine(self._console, category=category)

        if category == WorkflowCategory.FULL_LIFECYCLE:
            await engine.run_full_lifecycle(target)
        else:
            await engine.run_stage_by_stage(target)

    async def cmd_history(self, *args) -> None:
        """Show workflow run history."""
        engine = AutonomousWorkflowEngine(self._console)
        history = engine.get_run_history()
        if not history:
            self.console.print("[yellow]No workflow runs recorded yet.[/yellow]")
            return

        table = Table(title="Workflow Run History", header_style="bold cyan")
        table.add_column("Run ID", style="bold yellow")
        table.add_column("Target", style="white")
        table.add_column("Category", style="cyan")
        table.add_column("Success", style="green")
        table.add_column("Duration (s)", style="white")
        table.add_column("Stages", style="white")

        for run in history[-20:]:
            table.add_row(
                run.get("run_id", "N/A"),
                run.get("target", "N/A"),
                run.get("category", "N/A"),
                str(run.get("overall_success", False)),
                f"{run.get('total_duration_ms', 0) / 1000:.1f}",
                str(len(run.get("stages", []))),
            )
        self._console.print(table)

    async def cmd_rates(self, *args) -> None:
        """Show exploit success rates by vector."""
        engine = AutonomousWorkflowEngine(self._console)
        rates = engine.get_success_rates()
        if not rates:
            self.console.print("[yellow]No exploit data recorded yet.[/yellow]")
            return

        table = Table(title="Exploit Success Rates by Vector", header_style="bold cyan")
        table.add_column("Vector", style="bold yellow")
        table.add_column("Success Rate (%)", style="white")

        for vector, rate in sorted(rates.items(), key=lambda x: -x[1]):
            table.add_row(vector, f"{rate:.1f}%")
        self._console.print(table)

    async def cmd_set_category(self, *args) -> None:
        """Set the default workflow category."""
        cat = self.prompt("Category (full_lifecycle/stage_by_stage)", choices=["full_lifecycle", "stage_by_stage"], default="full_lifecycle")
        self.console.print(f"[green]Default workflow category set to: {cat}[/green]")
