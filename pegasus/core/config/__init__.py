"""
Pegasus Phantom Menace - Configuration System
Centralized configuration management with environment variable support.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


class AppSettings(BaseModel):
    """Application-level settings."""
    name: str = "Pegasus Phantom Menace"
    version: str = "2.0.0"
    debug: bool = False
    workspace: Path = Path.home() / ".pegasus"
    log_level: str = "INFO"
    log_format: str = "json"  # json, text, console


class DatabaseSettings(BaseModel):
    """Database configuration."""
    type: str = "sqlite"  # sqlite, postgresql
    path: Path = Path.home() / ".pegasus" / "pegasus.db"
    host: str = "localhost"
    port: int = 5432
    username: str = "pegasus"
    password: str = ""
    database: str = "pegasus"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

    @property
    def url(self) -> str:
        if self.type == "sqlite":
            return f"sqlite+aiosqlite:///{self.path}"
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class MetasploitSettings(BaseModel):
    """Metasploit RPC configuration."""
    rpc_host: str = "127.0.0.1"
    rpc_port: int = 55553
    rpc_password: str = "msf123"
    rpc_ssl: bool = False
    auto_start: bool = False
    timeout: int = 30


class FridaSettings(BaseModel):
    """Frida configuration."""
    enabled: bool = True
    scripts_dir: Path = Path.home() / ".pegasus" / "frida_scripts"
    default_timeout: int = 30


class AISettings(BaseModel):
    """AI/LLM configuration."""
    provider: str = "anthropic"  # anthropic, openai, local
    model: str = "claude-sonnet-4-6"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7
    cache_enabled: bool = True
    cache_ttl: int = 3600
    system_prompt: str = """You are Pegasus AI — an expert Android security and penetration testing assistant.
You assist authorised security professionals with:
- Android vulnerability assessment and penetration testing techniques
- ADB commands and device management
- Network security analysis and scanning
- Report writing and findings documentation
- Defensive recommendations and patch advice

You always remind users that testing must be authorised. You do not assist with
illegal activities. You provide technical, accurate, actionable advice."""


class NetworkSettings(BaseModel):
    """Network configuration."""
    default_interface: str = "auto"
    nmap_path: str = "nmap"
    default_timeout: int = 120
    default_ports: str = "1-1000"
    ping_timeout: float = 1.0


class ReportingSettings(BaseModel):
    """Reporting configuration."""
    default_format: str = "html"  # html, pdf, json, csv
    output_dir: Path = Path.home() / ".pegasus" / "reports"
    theme: str = "dark"  # dark, light
    template_dir: Optional[Path] = None
    auto_open: bool = False


class MetasploitSettings(BaseModel):
    """Metasploit RPC configuration."""
    rpc_host: str = "127.0.0.1"
    rpc_port: int = 55553
    rpc_password: str = "msf123"
    rpc_ssl: bool = False
    auto_start: bool = False
    timeout: int = 30


class FridaSettings(BaseModel):
    """Frida configuration."""
    enabled: bool = True
    scripts_dir: Path = Path.home() / ".pegasus" / "frida_scripts"
    default_timeout: int = 30


class SecuritySettings(BaseModel):
    """Security & authentication settings."""
    jwt_secret: str = Field(default_factory=lambda: os.urandom(32).hex())
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    jwt_refresh_expiry_days: int = 7
    bcrypt_rounds: int = 12
    api_rate_limit: int = 100  # requests per minute
    enable_2fa: bool = False
    webauthn_enabled: bool = False


class TelemetrySettings(BaseModel):
    """Telemetry & monitoring."""
    enabled: bool = False
    endpoint: str = ""
    interval: int = 300  # seconds
    include_system_info: bool = True
    anonymize: bool = True


class PluginSettings(BaseModel):
    """Plugin system configuration."""
    enabled: list[str] = ["core"]
    auto_load: bool = True
    plugin_dirs: list[Path] = Field(default_factory=lambda: [
        Path.home() / ".pegasus" / "plugins",
        Path(__file__).parent.parent / "plugins" / "core",
        Path(__file__).parent.parent / "plugins" / "community",
        Path(__file__).parent.parent / "plugins" / "enterprise",
    ])
    allow_external: bool = True


class Settings(BaseSettings):
    """Main settings class - combines all sub-settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
    
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    metasploit: MetasploitSettings = Field(default_factory=MetasploitSettings)
    frida: FridaSettings = Field(default_factory=FridaSettings)
    ai: AISettings = Field(default_factory=AISettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)
    reporting: ReportingSettings = Field(default_factory=ReportingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)

    @field_validator("app", "database", "metasploit", "frida", "ai", "network", "reporting", "security", "telemetry", "plugins", mode="before")
    @classmethod
    def validate_sub_settings(cls, v):
        if isinstance(v, dict):
            return v
        return v

    def get_workspace_path(self) -> Path:
        """Get the workspace path, creating if necessary."""
        path = self.app.workspace.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_payloads_dir(self) -> Path:
        path = self.get_workspace_path() / "payloads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_reports_dir(self) -> Path:
        path = self.get_workspace_path() / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_sessions_dir(self) -> Path:
        path = self.get_workspace_path() / "sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_logs_dir(self) -> Path:
        path = self.get_workspace_path() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_campaigns_dir(self) -> Path:
        path = self.get_workspace_path() / "campaigns"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_dna_dir(self) -> Path:
        path = self.get_workspace_path() / "dna"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_certs_dir(self) -> Path:
        path = self.get_workspace_path() / "certs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_cases_dir(self) -> Path:
        path = self.get_workspace_path() / "cases"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_forensics_dir(self) -> Path:
        path = self.get_workspace_path() / "forensics"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience function
def get_config() -> Settings:
    """Get the global settings instance."""
    return get_settings()


# Export commonly used paths
def get_workspace() -> Path:
    return get_settings().get_workspace_path()


def get_payloads_dir() -> Path:
    return get_settings().get_payloads_dir()


def get_reports_dir() -> Path:
    return get_settings().get_reports_dir()


def get_sessions_dir() -> Path:
    return get_settings().get_sessions_dir()


def get_logs_dir() -> Path:
    return get_settings().get_logs_dir()


def get_campaigns_dir() -> Path:
    return get_settings().get_campaigns_dir()


def get_dna_dir() -> Path:
    return get_settings().get_dna_dir()


def get_certs_dir() -> Path:
    return get_settings().get_certs_dir()


def get_cases_dir() -> Path:
    return get_settings().get_cases_dir()


def get_forensics_dir() -> Path:
    return get_settings().get_forensics_dir()