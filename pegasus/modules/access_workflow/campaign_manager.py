"""
Pegasus Phantom Menace v2 - Campaign Management System

Multi-target campaign management with:
- Campaign lifecycle management
- Target tracking and authorization
- Evidence collection and report generation
- Campaign analytics and metrics
- Authorization workflow
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3


class CampaignStatus(str, Enum):
    """Campaign status enumeration."""
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class TargetStatus(str, Enum):
    """Target status enumeration."""
    DISCOVERED = "discovered"
    SCOPED = "scoped"
    AUTHORIZED = "authorized"
    ACTIVE = "active"
    COMPROMISED = "compromised"
    PERSISTENT = "persistent"
    EXFILTRATED = "exfiltrated"
    LOST = "lost"
    BURNED = "burned"
    REMOVED = "removed"


class AuthorizationLevel(str, Enum):
    """Authorization levels for targets."""
    UNAUTHORIZED = "unauthorized"
    LIMITED = "limited"      # Limited scope testing
    FULL = "full"            # Full penetration test
    CRITICAL = "critical"    # Critical infrastructure testing
    EMERGENCY = "emergency"  # Emergency authorization


@dataclass
class Target:
    """Represents a target in a campaign."""
    target_id: str
    campaign_id: str
    name: str
    target_type: str  # device, network, application, person, organization
    target_value: str  # IP, domain, email, phone, etc.
    authorization_level: AuthorizationLevel = AuthorizationLevel.UNAUTHORIZED
    status: TargetStatus = TargetStatus.DISCOVERED
    priority: int = 1  # 1-10, 10 being highest
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authorized_at: Optional[str] = None
    compromised_at: Optional[str] = None
    persistent_at: Optional[str] = None
    exfiltrated_at: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)  # List of finding IDs
    sessions: List[str] = field(default_factory=list)  # List of session IDs


@dataclass
class Campaign:
    """Represents a penetration testing campaign."""
    campaign_id: str
    name: str
    description: str
    status: CampaignStatus = CampaignStatus.PLANNING
    author: str = "anonymous"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    authorization: Optional[str] = None  # Authorization document/reference
    scope: List[str] = field(default_factory=list)  # Authorized targets/scopes
    rules_of_engagement: Optional[str] = None
    targets: List[str] = field(default_factory=list)  # List of target IDs
    findings: List[str] = field(default_factory=list)  # List of finding IDs
    reports: List[str] = field(default_factory=list)  # List of report IDs
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    """Represents a security finding."""
    finding_id: str
    campaign_id: str
    target_id: str
    title: str
    description: str
    severity: str  # critical, high, medium, low, info
    cvss_score: Optional[float] = None
    cve_id: Optional[str] = None
    exploit_used: Optional[str] = None
    evidence: Optional[str] = None
    remediation: Optional[str] = None
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "open"  # open, mitigated, accepted, false_positive


@dataclass
class Report:
    """Represents a penetration testing report."""
    report_id: str
    campaign_id: str
    title: str
    author: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    format: str = "html"  # html, pdf, json, csv
    file_path: Optional[str] = None
    findings: List[str] = field(default_factory=list)  # List of finding IDs
    executive_summary: Optional[str] = None
    detailed_findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: Optional[str] = None


class CampaignManager:
    """
    Campaign management system for multi-target operations.
    
    Provides:
    - Campaign creation and lifecycle management
    - Target discovery, authorization, and tracking
    - Finding documentation and evidence collection
    - Report generation
    - Campaign analytics and metrics
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(os.path.expanduser("~"), ".pegasus", "campaigns.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True) if isinstance(self.db_path, Path) else None
        self._init_db()
        self._campaigns: Dict[str, Campaign] = {}
        self._targets: Dict[str, Target] = {}
        self._findings: Dict[str, Finding] = {}
        self._reports: Dict[str, Report] = {}
        self._load_from_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        db_path = Path(self.db_path) if isinstance(self.db_path, str) else self.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Campaigns table
        c.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                status TEXT,
                author TEXT,
                created_at TEXT,
                start_date TEXT,
                end_date TEXT,
                authorization TEXT,
                scope TEXT,
                rules_of_engagement TEXT,
                targets TEXT,
                findings TEXT,
                reports TEXT,
                metadata TEXT
            )
        """)
        
        # Targets table
        c.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                target_id TEXT PRIMARY KEY,
                campaign_id TEXT,
                name TEXT,
                target_type TEXT,
                target_value TEXT,
                authorization_level TEXT,
                status TEXT,
                priority INTEGER,
                discovered_at TEXT,
                authorized_at TEXT,
                compromised_at TEXT,
                persistent_at TEXT,
                exfiltrated_at TEXT,
                notes TEXT,
                metadata TEXT,
                findings TEXT,
                sessions TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
            )
        """)
        
        # Findings table
        c.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                finding_id TEXT PRIMARY KEY,
                campaign_id TEXT,
                target_id TEXT,
                title TEXT,
                description TEXT,
                severity TEXT,
                cvss_score REAL,
                cve_id TEXT,
                exploit_used TEXT,
                evidence TEXT,
                remediation TEXT,
                discovered_at TEXT,
                status TEXT
            )
        """)
        
        # Reports table
        c.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                campaign_id TEXT,
                title TEXT,
                author TEXT,
                generated_at TEXT,
                format TEXT,
                file_path TEXT,
                findings TEXT,
                executive_summary TEXT,
                detailed_findings TEXT,
                recommendations TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def _load_from_db(self):
        """Load all data from the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        
        # Load campaigns
        c.execute("SELECT * FROM campaigns")
        for row in c.fetchall():
            campaign = Campaign(
                campaign_id=row[0],
                name=row[1],
                description=row[2],
                status=CampaignStatus(row[3]),
                author=row[4],
                created_at=row[5],
                start_date=row[6],
                end_date=row[7],
                authorization=row[8],
                scope=json.loads(row[9]) if row[9] else [],
                rules_of_engagement=row[10],
                targets=json.loads(row[11]) if row[11] else [],
                findings=json.loads(row[12]) if row[12] else [],
                reports=json.loads(row[13]) if row[13] else [],
                metadata=json.loads(row[14]) if row[14] else {},
            )
            self._campaigns[campaign.campaign_id] = campaign
        
        # Load targets
        c.execute("SELECT * FROM targets")
        for row in c.fetchall():
            target = Target(
                target_id=row[0],
                campaign_id=row[1],
                name=row[2],
                target_type=row[3],
                target_value=row[4],
                authorization_level=AuthorizationLevel(row[5]),
                status=TargetStatus(row[6]),
                priority=row[7],
                discovered_at=row[8],
                authorized_at=row[9],
                compromised_at=row[10],
                persistent_at=row[11],
                exfiltrated_at=row[12],
                notes=row[13],
                metadata=json.loads(row[14]) if row[14] else {},
                findings=json.loads(row[15]) if row[15] else [],
                sessions=json.loads(row[16]) if row[16] else [],
            )
            self._targets[target.target_id] = target
        
        # Load findings
        c.execute("SELECT * FROM findings")
        for row in c.fetchall():
            finding = Finding(
                finding_id=row[0],
                campaign_id=row[1],
                target_id=row[2],
                title=row[3],
                description=row[4],
                severity=row[5],
                cvss_score=row[6],
                cve_id=row[7],
                exploit_used=row[8],
                evidence=row[9],
                remediation=row[10],
                discovered_at=row[11],
                status=row[12],
            )
            self._findings[finding.finding_id] = finding
        
        # Load reports
        c.execute("SELECT * FROM reports")
        for row in c.fetchall():
            report = Report(
                report_id=row[0],
                campaign_id=row[1],
                title=row[2],
                author=row[3],
                generated_at=row[4],
                format=row[5],
                file_path=row[6],
                findings=json.loads(row[7]) if row[7] else [],
                executive_summary=row[8],
                detailed_findings=json.loads(row[9]) if row[9] else [],
                recommendations=row[10],
            )
            self._reports[report.report_id] = report
        
        conn.close()

    def _save_campaign(self, campaign: Campaign):
        """Save a campaign to the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO campaigns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign.campaign_id,
            campaign.name,
            campaign.description,
            campaign.status.value,
            campaign.author,
            campaign.created_at,
            campaign.start_date,
            campaign.end_date,
            campaign.authorization,
            json.dumps(campaign.scope),
            campaign.rules_of_engagement,
            json.dumps(campaign.targets),
            json.dumps(campaign.findings),
            json.dumps(campaign.reports),
            json.dumps(campaign.metadata),
        ))
        conn.commit()
        conn.close()

    def _save_target(self, target: Target):
        """Save a target to the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO targets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            target.target_id,
            target.campaign_id,
            target.name,
            target.target_type,
            target.target_value,
            target.authorization_level.value,
            target.status.value,
            target.priority,
            target.discovered_at,
            target.authorized_at,
            target.compromised_at,
            target.persistent_at,
            target.exfiltrated_at,
            target.notes,
            json.dumps(target.metadata),
            json.dumps(target.findings),
            json.dumps(target.sessions),
        ))
        conn.commit()
        conn.close()

    def _save_finding(self, finding: Finding):
        """Save a finding to the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO findings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            finding.finding_id,
            finding.campaign_id,
            finding.target_id,
            finding.title,
            finding.description,
            finding.severity,
            finding.cvss_score,
            finding.cve_id,
            finding.exploit_used,
            finding.evidence,
            finding.remediation,
            finding.discovered_at,
            finding.status,
        ))
        conn.commit()
        conn.close()

    def _save_report(self, report: Report):
        """Save a report to the database."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.report_id,
            report.campaign_id,
            report.title,
            report.author,
            report.generated_at,
            report.format,
            report.file_path,
            json.dumps(report.findings),
            report.executive_summary,
            json.dumps(report.detailed_findings),
            report.recommendations,
        ))
        conn.commit()
        conn.close()

    # === Campaign Management ============================================

    def create_campaign(
        self,
        name: str,
        description: str,
        author: str = "anonymous",
        status: CampaignStatus = CampaignStatus.PLANNING,
        targets: Optional[List[str]] = None,
        **kwargs
    ) -> Campaign:
        """Create a new campaign."""
        campaign = Campaign(
            campaign_id=str(uuid.uuid4()),
            name=name,
            description=description,
            status=status,
            author=author,
            targets=targets or [],
            **kwargs,
        )
        self._campaigns[campaign.campaign_id] = campaign
        self._save_campaign(campaign)
        return campaign

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get a campaign by ID."""
        return self._campaigns.get(campaign_id)

    def list_campaigns(self) -> List[Campaign]:
        """List all campaigns."""
        return list(self._campaigns.values())

    def update_campaign(self, campaign: Campaign):
        """Update a campaign."""
        self._campaigns[campaign.campaign_id] = campaign
        self._save_campaign(campaign)

    def delete_campaign(self, campaign_id: str):
        """Delete a campaign."""
        if campaign_id in self._campaigns:
            del self._campaigns[campaign_id]
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute("DELETE FROM campaigns WHERE campaign_id = ?", (campaign_id,))
            conn.commit()
            conn.close()

    # === Target Management ==============================================

    def create_target(
        self,
        campaign_id: str,
        name: str,
        target_type: str,
        target_value: str,
        authorization_level: AuthorizationLevel = AuthorizationLevel.UNAUTHORIZED,
        priority: int = 1,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Target:
        """Create a new target."""
        target = Target(
            target_id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            name=name,
            target_type=target_type,
            target_value=target_value,
            authorization_level=authorization_level,
            priority=priority,
            notes=notes,
            metadata=metadata or {},
        )
        self._targets[target.target_id] = target
        self._save_target(target)
        
        # Add target to campaign
        if campaign_id in self._campaigns:
            campaign = self._campaigns[campaign_id]
            if target.target_id not in campaign.targets:
                campaign.targets.append(target.target_id)
                self._save_campaign(campaign)
        
        return target

    def get_target(self, target_id: str) -> Optional[Target]:
        """Get a target by ID."""
        return self._targets.get(target_id)

    def list_targets(self, campaign_id: Optional[str] = None) -> List[Target]:
        """List all targets, optionally filtered by campaign."""
        if campaign_id:
            return [t for t in self._targets.values() if t.campaign_id == campaign_id]
        return list(self._targets.values())

    def update_target(self, target: Target):
        """Update a target."""
        self._targets[target.target_id] = target
        self._save_target(target)

    def authorize_target(self, target_id: str, authorization_level: AuthorizationLevel):
        """Authorize a target for testing."""
        if target_id in self._targets:
            target = self._targets[target_id]
            target.authorization_level = authorization_level
            target.authorized_at = datetime.now(timezone.utc).isoformat()
            self._save_target(target)

    def compromise_target(self, target_id: str):
        """Mark a target as compromised."""
        if target_id in self._targets:
            target = self._targets[target_id]
            target.status = TargetStatus.COMPROMISED
            target.compromised_at = datetime.now(timezone.utc).isoformat()
            self._save_target(target)

    def persist_target(self, target_id: str):
        """Mark a target as having persistent access."""
        if target_id in self._targets:
            target = self._targets[target_id]
            target.status = TargetStatus.PERSISTENT
            target.persistent_at = datetime.now(timezone.utc).isoformat()
            self._save_target(target)

    def exfiltrate_target(self, target_id: str):
        """Mark a target as exfiltrated."""
        if target_id in self._targets:
            target = self._targets[target_id]
            target.status = TargetStatus.EXFILTRATED
            target.exfiltrated_at = datetime.now(timezone.utc).isoformat()
            self._save_target(target)

    # === Finding Management =============================================

    def create_finding(
        self,
        campaign_id: str,
        target_id: str,
        title: str,
        description: str,
        severity: str,
        cvss_score: Optional[float] = None,
        cve_id: Optional[str] = None,
        exploit_used: Optional[str] = None,
        evidence: Optional[str] = None,
        remediation: Optional[str] = None,
    ) -> Finding:
        """Create a new finding."""
        finding = Finding(
            finding_id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            target_id=target_id,
            title=title,
            description=description,
            severity=severity,
            cvss_score=cvss_score,
            cve_id=cve_id,
            exploit_used=exploit_used,
            evidence=evidence,
            remediation=remediation,
        )
        self._findings[finding.finding_id] = finding
        self._save_finding(finding)
        
        # Add finding to campaign
        if campaign_id in self._campaigns:
            campaign = self._campaigns[campaign_id]
            if finding.finding_id not in campaign.findings:
                campaign.findings.append(finding.finding_id)
                self._save_campaign(campaign)
        
        # Add finding to target
        if target_id in self._targets:
            target = self._targets[target_id]
            if finding.finding_id not in target.findings:
                target.findings.append(finding.finding_id)
                self._save_target(target)
        
        return finding

    def get_finding(self, finding_id: str) -> Optional[Finding]:
        """Get a finding by ID."""
        return self._findings.get(finding_id)

    def list_findings(self, campaign_id: Optional[str] = None, target_id: Optional[str] = None) -> List[Finding]:
        """List all findings, optionally filtered by campaign or target."""
        findings = list(self._findings.values())
        if campaign_id:
            findings = [f for f in findings if f.campaign_id == campaign_id]
        if target_id:
            findings = [f for f in findings if f.target_id == target_id]
        return findings

    # === Report Management ==============================================

    def create_report(
        self,
        campaign_id: str,
        title: str,
        author: str,
        format: str = "html",
        findings: Optional[List[str]] = None,
        executive_summary: Optional[str] = None,
        detailed_findings: Optional[List[Dict[str, Any]]] = None,
        recommendations: Optional[str] = None,
    ) -> Report:
        """Create a new report."""
        report = Report(
            report_id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            title=title,
            author=author,
            format=format,
            findings=findings or [],
            executive_summary=executive_summary,
            detailed_findings=detailed_findings or [],
            recommendations=recommendations,
        )
        self._reports[report.report_id] = report
        self._save_report(report)
        
        # Add report to campaign
        if campaign_id in self._campaigns:
            campaign = self._campaigns[campaign_id]
            if report.report_id not in campaign.reports:
                campaign.reports.append(report.report_id)
                self._save_campaign(campaign)
        
        return report

    def get_report(self, report_id: str) -> Optional[Report]:
        """Get a report by ID."""
        return self._reports.get(report_id)

    def list_reports(self, campaign_id: Optional[str] = None) -> List[Report]:
        """List all reports, optionally filtered by campaign."""
        if campaign_id:
            return [r for r in self._reports.values() if r.campaign_id == campaign_id]
        return list(self._reports.values())

    # === Analytics =======================================================

    def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Get statistics for a campaign."""
        if campaign_id not in self._campaigns:
            return {}
        
        campaign = self._campaigns[campaign_id]
        targets = [t for t in self._targets.values() if t.campaign_id == campaign_id]
        findings = [f for f in self._findings.values() if f.campaign_id == campaign_id]
        reports = [r for r in self._reports.values() if r.campaign_id == campaign_id]
        
        return {
            "campaign_id": campaign_id,
            "name": campaign.name,
            "status": campaign.status.value,
            "total_targets": len(targets),
            "compromised_targets": len([t for t in targets if t.status == TargetStatus.COMPROMISED]),
            "persistent_targets": len([t for t in targets if t.status == TargetStatus.PERSISTENT]),
            "exfiltrated_targets": len([t for t in targets if t.status == TargetStatus.EXFILTRATED]),
            "total_findings": len(findings),
            "critical_findings": len([f for f in findings if f.severity == "critical"]),
            "high_findings": len([f for f in findings if f.severity == "high"]),
            "total_reports": len(reports),
            "created_at": campaign.created_at,
            "start_date": campaign.start_date,
            "end_date": campaign.end_date,
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global statistics across all campaigns."""
        return {
            "total_campaigns": len(self._campaigns),
            "active_campaigns": len([c for c in self._campaigns.values() if c.status == CampaignStatus.ACTIVE]),
            "total_targets": len(self._targets),
            "compromised_targets": len([t for t in self._targets.values() if t.status == TargetStatus.COMPROMISED]),
            "persistent_targets": len([t for t in self._targets.values() if t.status == TargetStatus.PERSISTENT]),
            "exfiltrated_targets": len([t for t in self._targets.values() if t.status == TargetStatus.EXFILTRATED]),
            "total_findings": len(self._findings),
            "total_reports": len(self._reports),
        }


# Global campaign manager instance
campaign_manager = CampaignManager()

def get_campaign_manager() -> CampaignManager:
    """Get the global campaign manager."""
    return campaign_manager