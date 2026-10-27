"""
Pegasus Phantom Menace v2 - Database Session & Connection Management
SQLAlchemy async engine, session factory, and database initialization.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from pegasus_v2.core.config import get_settings
from pegasus_v2.core.db.models import Base

logger = logging.getLogger("pegasus.db")


# ---------------------------------------------------------------------------
# Global engine/session holders (initialized on startup)
# ---------------------------------------------------------------------------

_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_sync_engine = None
_sync_session_factory = None


def get_engine():
    """Return the async SQLAlchemy engine (initializes lazily)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        database_url = settings.database.url
        _engine = create_async_engine(
            database_url,
            echo=settings.database.echo,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,
        )
    return _engine


def get_sync_engine():
    """Return a synchronous SQLAlchemy engine (for migrations/scripts)."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        # Convert async URL to sync
        url = settings.database.url
        if url.startswith("sqlite+aiosqlite:///"):
            sync_url = url.replace("sqlite+aiosqlite:///", "sqlite:///")
        elif url.startswith("postgresql+asyncpg://"):
            sync_url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        else:
            sync_url = url
        _sync_engine = create_engine(sync_url, echo=settings.database.echo)
    return _sync_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


def get_sync_session_factory():
    """Return the synchronous session factory."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=get_sync_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sync_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding a database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database: create tables, run seed data."""
    global _engine
    settings = get_settings()
    _engine = create_async_engine(
        settings.database.url,
        echo=settings.database.echo,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=True,
    )

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized: %s", settings.database.url)

    # Seed default data if needed
    await _seed_default_data()


async def _seed_default_data() -> None:
    """Seed default vulnerability database and settings."""
    from pegasus_v2.core.db.models import Vulnerability
    from sqlalchemy import select

    async with get_session() as session:
        # Check if vulnerabilities already seeded
        result = await session.execute(select(Vulnerability).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # Already seeded

        default_cves = [
            {
                "cve_id": "CVE-2024-31317",
                "title": "ZygoteProcess command injection — system-level code execution",
                "description": "A vulnerability in ZygoteProcess allows arbitrary code execution at system level.",
                "severity": "critical",
                "cvss_score": 9.8,
                "affected_api_min": 30,
                "affected_api_max": 34,
                "patch_level": "2024-07-01",
                "exploit_available": True,
            },
            {
                "cve_id": "CVE-2024-0044",
                "title": "run-as privilege escalation via PackageManager race condition",
                "description": "Race condition in PackageManager allows privilege escalation.",
                "severity": "high",
                "cvss_score": 7.7,
                "affected_api_min": 31,
                "affected_api_max": 34,
                "patch_level": "2024-06-01",
                "exploit_available": False,
            },
            {
                "cve_id": "CVE-2023-21492",
                "title": "Kernel information disclosure via race condition",
                "description": "Kernel race condition allows information disclosure.",
                "severity": "high",
                "cvss_score": 7.4,
                "affected_api_min": 28,
                "affected_api_max": 33,
                "patch_level": "2023-05-01",
                "exploit_available": False,
            },
            {
                "cve_id": "CVE-2023-20963",
                "title": "WorkSource privilege escalation",
                "description": "WorkSource privilege escalation allows app to run as system.",
                "severity": "high",
                "cvss_score": 7.8,
                "affected_api_min": 30,
                "affected_api_max": 33,
                "patch_level": "2023-03-01",
                "exploit_available": False,
            },
            {
                "cve_id": "CVE-2022-20465",
                "title": "Lockscreen bypass — access device without PIN",
                "description": "Lockscreen bypass allows access without PIN authentication.",
                "severity": "critical",
                "cvss_score": 9.1,
                "affected_api_min": 30,
                "affected_api_max": 32,
                "patch_level": "2022-11-01",
                "exploit_available": True,
            },
            {
                "cve_id": "CVE-2022-20452",
                "title": "Permission bypass in NotificationManager",
                "description": "NotificationManager permission bypass leads to privilege escalation.",
                "severity": "high",
                "cvss_score": 8.4,
                "affected_api_min": 30,
                "affected_api_max": 33,
                "patch_level": "2022-12-01",
                "exploit_available": False,
            },
            {
                "cve_id": "CVE-2021-39793",
                "title": "GPU driver heap OOB write",
                "description": "GPU driver heap out-of-bounds write allows local privilege escalation.",
                "severity": "critical",
                "cvss_score": 8.8,
                "affected_api_min": 26,
                "affected_api_max": 32,
                "patch_level": "2022-03-05",
                "exploit_available": True,
            },
            {
                "cve_id": "CVE-2021-0954",
                "title": "Intent redirection in Android framework",
                "description": "Intent redirection vulnerability in Android framework.",
                "severity": "high",
                "cvss_score": 7.3,
                "affected_api_min": 26,
                "affected_api_max": 31,
                "patch_level": "2021-12-01",
                "exploit_available": False,
            },
            {
                "cve_id": "CVE-2020-0041",
                "title": "Binder OOB write — full root exploit chain",
                "description": "Binder out-of-bounds write allows full root exploit chain.",
                "severity": "critical",
                "cvss_score": 9.8,
                "affected_api_min": 26,
                "affected_api_max": 29,
                "patch_level": "2020-03-01",
                "exploit_available": True,
            },
            {
                "cve_id": "CVE-2019-2215",
                "title": "Use-after-free in Binder IPC driver",
                "description": "Use-after-free in Binder IPC driver used in in-the-wild exploits.",
                "severity": "critical",
                "cvss_score": 9.3,
                "affected_api_min": 21,
                "affected_api_max": 28,
                "patch_level": "2019-10-06",
                "exploit_available": True,
            },
            {
                "cve_id": "CVE-2017-13156",
                "title": "Janus vulnerability — APK signature bypass",
                "description": "Janus vulnerability allows APK signature bypass and code injection.",
                "severity": "high",
                "cvss_score": 7.8,
                "affected_api_min": 21,
                "affected_api_max": 26,
                "patch_level": "2017-12-01",
                "exploit_available": True,
            },
            {
                "cve_id": "CVE-2015-3864",
                "title": "Stagefright — MMS media processing RCE",
                "description": "Stagefright MMS media processing remote code execution.",
                "severity": "critical",
                "cvss_score": 10.0,
                "affected_api_min": 16,
                "affected_api_max": 22,
                "patch_level": "2015-09-01",
                "exploit_available": True,
            },
        ]

        for cve_data in default_cves:
            vuln = Vulnerability(**cve_data)
            session.add(vuln)

        await session.commit()
        logger.info("Seeded %d default CVEs", len(default_cves))


async def close_db() -> None:
    """Close database connections."""
    global _engine, _sync_engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None


# ---------------------------------------------------------------------------
# Dependency injection helper (for FastAPI)
# ---------------------------------------------------------------------------

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield a database session."""
    async with get_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Migration helper (alembic)
# ---------------------------------------------------------------------------

def get_sync_session():
    """Synchronous session context manager for scripts/migrations."""
    factory = get_sync_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables_sync() -> None:
    """Create all tables synchronously (for testing/scripts)."""
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created (sync)")


def drop_all_tables_sync() -> None:
    """Drop all tables synchronously (for testing)."""
    engine = get_sync_engine()
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped (sync)")