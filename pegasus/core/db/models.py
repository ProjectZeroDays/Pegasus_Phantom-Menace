#!/usr/bin/env python3
"""Pegasus Phantom Menace v2 - Database Models"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
    Boolean,
    Float,
    Enum,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

Base = declarative_base()


class DeviceStatus(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    ROOTED = "rooted"
    UNKNOWN = "unknown"


class SessionType(str, enum.Enum):
    METERPRETER = "meterpreter"
    SHELL = "shell"
    WEBCAM = "webcam"
    MICROPHONE = "microphone"
    UNKNOWN = "unknown"


class PayloadType(str, enum.Enum):
    REVERSE_TCP = "reverse_tcp"
    REVERSE_HTTPS = "reverse_https"
    REVERSE_HTTP = "reverse_http"
    BIND_TCP = "bind_tcp"
    SHELL_REVERSE_TCP = "shell_reverse_tcp"
    BIND_SHELL = "bind_shell"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReportFormat(str, enum.Enum):
    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"


class CampaignStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class VulnSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class SteganographyFormat(str, enum.Enum):
    PNG = "png"
    JPEG = "jpeg"
    BMP = "bmp"
    GIF = "gif"


class ConnectionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    serial: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    android_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    api_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    security_patch: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus), default=DeviceStatus.DISCONNECTED, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    battery_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_free: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_rooted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_debuggable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_disconnected: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    connection_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_uptime_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="device", cascade="all, delete-orphan")
    connections: Mapped[list["ConnectionLog"]] = relationship("ConnectionLog", back_populates="device", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="device", cascade="all, delete-orphan")
    vulnerabilities: Mapped[list["DeviceVulnerability"]] = relationship("DeviceVulnerability", back_populates="device", cascade="all, delete-orphan")
    payloads: Mapped[list["Payload"]] = relationship("Payload", back_populates="device", cascade="all, delete-orphan")
    screenshots: Mapped[list["Screenshot"]] = relationship("Screenshot", back_populates="device", cascade="all, delete-orphan")
    extractions: Mapped[list["Extraction"]] = relationship("Extraction", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_devices_status", "status"),
        Index("idx_devices_manufacturer_model", "manufacturer", "model"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), default=SessionType.METERPRETER, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    local_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    local_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remote_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    remote_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tunnel_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    keepalive_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    keepalive_interval: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    command_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_command_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    device: Mapped[Device] = relationship("Device", back_populates="sessions")
    commands: Mapped[list["SessionCommand"]] = relationship("SessionCommand", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sessions_device_status", "device_id", "status"),
        Index("idx_sessions_type", "session_type"),
    )


class SessionCommand(Base):
    __tablename__ = "session_commands"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped[Session] = relationship("Session", back_populates="commands")

    __table_args__ = (
        Index("idx_session_commands_session_created", "session_id", "created_at"),
    )


class ConnectionLog(Base):
    __tablename__ = "connection_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[ConnectionStatus] = mapped_column(Enum(ConnectionStatus), nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    device: Mapped[Device] = relationship("Device", back_populates="connections")

    __table_args__ = (
        Index("idx_connection_logs_device_created", "device_id", "connected_at"),
    )


class Payload(Base):
    __tablename__ = "payloads"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    payload_type: Mapped[PayloadType] = mapped_column(Enum(PayloadType), nullable=False)
    lhost: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    lport: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    encoder: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    iterations: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    dna_tag: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    target_device_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    campaign_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    is_delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delivery_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    device: Mapped[Optional[Device]] = relationship("Device", back_populates="payloads")
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", back_populates="payloads")

    __table_args__ = (
        Index("idx_payloads_type_status", "payload_type", "is_delivered"),
        Index("idx_payloads_dna", "dna_tag"),
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(Enum(FindingSeverity), default=FindingSeverity.INFO, nullable=False)
    cvss_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cve_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    remediation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    references: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    is_false_positive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    device: Mapped[Device] = relationship("Device", back_populates="findings")
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", back_populates="findings")

    __table_args__ = (
        Index("idx_findings_device_severity", "device_id", "severity"),
        Index("idx_findings_cve", "cve_id"),
    )


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    cve_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[VulnSeverity] = mapped_column(Enum(VulnSeverity), nullable=False)
    cvss_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    affected_api_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    affected_api_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patch_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    references: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    exploit_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    devices: Mapped[list["DeviceVulnerability"]] = relationship("DeviceVulnerability", back_populates="vulnerability")

    __table_args__ = (
        Index("idx_vulnerabilities_severity", "severity"),
        Index("idx_vulnerabilities_cve", "cve_id"),
    )


class DeviceVulnerability(Base):
    __tablename__ = "device_vulnerabilities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    vulnerability_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False, index=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    device: Mapped["Device"] = relationship("Device", back_populates="vulnerabilities")
    vulnerability: Mapped["Vulnerability"] = relationship("Vulnerability", back_populates="devices")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    format: Mapped[str] = mapped_column(String(20), default="png", nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    device: Mapped[Device] = relationship("Device", back_populates="screenshots")


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    destination_path: Mapped[str] = mapped_column(String(500), nullable=False)
    extraction_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    device: Mapped[Device] = relationship("Device", back_populates="extractions")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.ACTIVE, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    authorization: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    targets: Mapped[list["CampaignTarget"]] = relationship("CampaignTarget", back_populates="campaign", cascade="all, delete-orphan")
    payloads: Mapped[list[Payload]] = relationship("Payload", back_populates="campaign")
    findings: Mapped[list[Finding]] = relationship("Finding", back_populates="campaign")
    reports: Mapped[list["Report"]] = relationship("Report", back_populates="campaign", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_campaigns_status", "status"),
        Index("idx_campaigns_author", "author"),
    )


class CampaignTarget(Base):
    __tablename__ = "campaign_targets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_value: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="targets")

    __table_args__ = (
        UniqueConstraint("campaign_id", "target_value", name="uq_campaign_target"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    campaign_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    tester: Mapped[str] = mapped_column(String(255), nullable=False)
    target: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[ReportFormat] = mapped_column(Enum(ReportFormat), default=ReportFormat.HTML, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payloads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    campaign: Mapped[Optional[Campaign]] = relationship("Campaign", back_populates="reports")
    report_findings: Mapped[list["ReportFinding"]] = relationship("ReportFinding", back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_reports_campaign_format", "campaign_id", "format"),
        Index("idx_reports_generated", "generated_at"),
    )


class ReportFinding(Base):
    __tablename__ = "report_findings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)

    report: Mapped["Report"] = relationship("Report", back_populates="report_findings")
    finding: Mapped["Finding"] = relationship("Finding")

    __table_args__ = (
        UniqueConstraint("report_id", "finding_id", name="uq_report_finding"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="analyst", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_factor_secret: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # --- access control -------------------------------------------------
    passkey_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fido2_credential_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fido2_public_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wallet_address: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    access_tier: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    access_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_active", "is_active"),
        Index("idx_users_approval", "approval_status"),
    )


class AppSetting(Base):
    """Key/value store for runtime configuration (admin wallet, pricing)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Payment(Base):
    """A USDC subscription payment claim and its verification state."""

    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_usdc: Mapped[float] = mapped_column(Float, nullable=False)
    wallet_from: Mapped[str] = mapped_column(String(128), nullable=False)
    wallet_to: Mapped[str] = mapped_column(String(128), nullable=False)
    tx_ref: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_payments_user_status", "user_id", "status"),
    )


class Notification(Base):
    """Admin inbox entries (registration requests, payments, system events)."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_notifications_kind_created", "kind", "created_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
        Index("idx_audit_logs_action", "action"),
    )


class IOC(Base):
    __tablename__ = "iocs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    ioc_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    threat_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_iocs_type_value", "ioc_type", "value"),
        Index("idx_iocs_source", "source"),
    )
