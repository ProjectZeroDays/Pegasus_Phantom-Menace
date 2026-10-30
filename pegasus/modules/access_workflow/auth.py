"""
Pegasus Phantom Menace v2 - Accounts, Approval and USDC Access Control

SQLite-backed auth for the dashboard:

* first-run admin bootstrap (password + passkey, optional FIDO2)
* self-service registration with admin approval queue
* one-time / weekly / monthly access paid in USDC to the admin wallet
* on-chain verification through Blockscout (no API key), with manual confirm

Passwords use PBKDF2-HMAC-SHA256 at 260k iterations. Passkeys are random
secrets stored as hashes. FIDO2 is used only when the ``fido2`` package is
installed; otherwise the passkey factor stands alone.

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from pegasus.core.config import get_settings
from pegasus.core.db.models import AppSetting, Base, Notification, Payment, User

PBKDF2_ROUNDS = 260_000
BLOCKSCOUT = "https://eth.blockscout.com/api/v2/addresses/{address}/token-transfers?type=ERC-20"
USDC_SYMBOL = "USDC"
WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
SESSION_USER_KEY = "pegasus_user_id"

_db_path = Path(get_settings().database.path).expanduser()
_db_path.parent.mkdir(parents=True, exist_ok=True)

_engine = create_engine(f"sqlite:///{_db_path}", future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


class AuthError(RuntimeError):
    """Raised for validation and credential failures."""


def _uuid(value: Any) -> Any:
    """Coerce a string to UUID for SQLAlchemy's UUID columns."""
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return value


@dataclass(frozen=True)
class Tier:
    key: str
    label: str
    amount_usdc: float
    duration_days: int
    description: str


TIERS: Dict[str, Tier] = {
    "one_time": Tier("one_time", "One-time access", 100.0, 30, "Single 30-day activation, no renewal."),
    "weekly": Tier("weekly", "Weekly", 100.0, 7, "Seven days of access, renew weekly."),
    "monthly": Tier("monthly", "Monthly", 100.0, 30, "Thirty days of access, best value cadence."),
}

ADDONS: Dict[str, Tier] = {
    "device_audit": Tier("device_audit", "Guided device audit", 150.0, 0, "Operator-assisted audit of one device."),
    "payload_pack": Tier("payload_pack", "Payload pack", 75.0, 0, "Custom mutation and stego pack for one campaign."),
}


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if len(password) < 4:
        raise AuthError("Password must be at least 4 characters")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
    return hmac.compare_digest(candidate, digest)


def hash_passkey(passkey: str) -> str:
    return "sha256$" + hashlib.sha256(passkey.encode()).hexdigest()


def verify_passkey(passkey: str, stored: Optional[str]) -> bool:
    if not stored:
        return True  # passkey not enrolled
    return hmac.compare_digest("sha256$" + hashlib.sha256(passkey.encode()).hexdigest(), stored)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_auth_db() -> None:
    _sqlite_migrate()
    Base.metadata.create_all(bind=_engine)
    with session_scope() as session:
        _seed_demo(session)


USER_COLUMN_MIGRATIONS = {
    "passkey_hash": "VARCHAR(255)",
    "fido2_credential_id": "TEXT",
    "fido2_public_key": "TEXT",
    "wallet_address": "VARCHAR(128)",
    "approval_status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
    "access_tier": "VARCHAR(20) NOT NULL DEFAULT 'none'",
    "access_expires_at": "DATETIME",
    "is_demo": "BOOLEAN NOT NULL DEFAULT 0",
}


def _sqlite_migrate() -> None:
    """Add auth columns to a pre-existing users table (idempotent)."""
    if not _db_path.exists():
        return
    with _engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        if not rows:
            return
        present = {row[1] for row in rows}
        for column, ddl in USER_COLUMN_MIGRATIONS.items():
            if column not in present:
                connection.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {column} {ddl}")


def _seed_demo(session: Session) -> None:
    existing = session.scalar(select(User).where(User.username == "demo"))
    if existing:
        return
    demo = User(
        username="demo",
        email="demo@pegasus.local",
        password_hash=hash_password("demo"),
        role="analyst",
        approval_status="approved",
        access_tier="demo",
        access_expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
        is_demo=True,
        wallet_address="0x000000000000000000000000000000000000dEaD",
    )
    session.add(demo)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "admin_wallet": "",
    "registration_open": "0",
    "chain": "ethereum",
    "price_one_time": "100",
    "price_weekly": "100",
    "price_monthly": "100",
    "payment_note": "Send the exact USDC amount from the wallet you registered.",
}


def get_setting(session: Session, key: str, default: str = "") -> str:
    row = session.get(AppSetting, key)
    return row.value if row and row.value is not None else DEFAULT_SETTINGS.get(key, default)


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        session.add(AppSetting(key=key, value=value))


def tier_price(session: Session, key: str) -> float:
    tier = TIERS.get(key) or ADDONS.get(key)
    if not tier:
        raise AuthError(f"Unknown service: {key}")
    return float(get_setting(session, f"price_{key}", str(tier.amount_usdc)))


def needs_setup() -> bool:
    with session_scope() as session:
        admin = session.scalar(select(User).where(User.role == "admin"))
        return admin is None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def create_admin(username: str, email: str, password: str, passkey: str, wallet: str = "") -> User:
    if not WALLET_RE.match(wallet or ""):
        raise AuthError("Admin wallet must be a 0x-prefixed 40-hex Ethereum address")
    if not passkey or len(passkey) < 10:
        raise AuthError("Passkey must be at least 10 characters")
    with session_scope() as session:
        if session.scalar(select(User).where(User.role == "admin")):
            raise AuthError("An admin already exists")
        user = User(
            username=username.strip(),
            email=email.strip().lower(),
            password_hash=hash_password(password),
            passkey_hash=hash_passkey(passkey),
            wallet_address=wallet,
            role="admin",
            approval_status="approved",
            access_tier="admin",
            access_expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
        )
        session.add(user)
        session.flush()
        set_setting(session, "admin_wallet", wallet)
        set_setting(session, "registration_open", "1")
        session.add(Notification(kind="system", title="Admin account created", body=f"Operator {username} bootstrapped the instance."))
        session.refresh(user)
        return user


def register_user(username: str, email: str, password: str, wallet: str = "", note: str = "") -> User:
    username = username.strip()
    email = email.strip().lower()
    if not re.match(r"^[a-zA-Z0-9_.-]{3,32}$", username):
        raise AuthError("Username must be 3-32 characters (letters, digits, . _ -)")
    if "@" not in email:
        raise AuthError("A valid email is required")
    if wallet and not WALLET_RE.match(wallet):
        raise AuthError("Wallet must be a 0x-prefixed 40-hex address")
    with session_scope() as session:
        if get_setting(session, "registration_open") != "1":
            raise AuthError("Registration is closed; ask the operator for a passkey")
        if session.scalar(select(User).where(func.lower(User.username) == username.lower())):
            raise AuthError("Username already taken")
        if session.scalar(select(User).where(User.email == email)):
            raise AuthError("Email already registered")
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            wallet_address=wallet or None,
            approval_status="pending",
            access_tier="none",
        )
        session.add(user)
        session.flush()
        session.add(Notification(
            kind="registration",
            title=f"New account: {username}",
            body=note or f"{email} requested access.",
            user_id=user.id,
        ))
        session.refresh(user)
        return user


def authenticate(username: str, password: str, passkey: Optional[str] = None) -> User:
    with session_scope() as session:
        user = session.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))
        if not user or not verify_password(password, user.password_hash):
            raise AuthError("Invalid credentials")
        if not user.is_active:
            raise AuthError("Account disabled")
        if user.passkey_hash and not verify_passkey(passkey or "", user.passkey_hash):
            raise AuthError("Passkey required")
        user.last_login_at = datetime.now(timezone.utc)
        session.flush()
        session.refresh(user)
        return user


def get_user(user_id: str) -> Optional[User]:
    try:
        with session_scope() as session:
            return session.get(User, _uuid(user_id))
    except Exception:
        return None


def approve_user(user_id: str) -> None:
    with session_scope() as session:
        user = session.get(User, _uuid(user_id))
        if not user:
            raise AuthError("User not found")
        user.approval_status = "approved"
        session.add(Notification(kind="system", title=f"Approved {user.username}", body="User may now pay for access.", user_id=user.id))


def reject_user(user_id: str) -> None:
    with session_scope() as session:
        user = session.get(User, _uuid(user_id))
        if not user:
            raise AuthError("User not found")
        user.approval_status = "rejected"
        user.is_active = False


def pending_users() -> List[User]:
    with session_scope() as session:
        return list(session.scalars(select(User).where(User.approval_status == "pending").order_by(User.created_at)))


def all_users() -> List[User]:
    with session_scope() as session:
        return list(session.scalars(select(User).order_by(User.created_at.desc())))


def is_active_subscriber(user: User) -> bool:
    if user.is_demo or user.role == "admin":
        return True
    if user.access_tier == "none":
        return False
    if user.access_expires_at is None:
        return False
    expires = user.access_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > datetime.now(timezone.utc)


def activate_tier(user_id: str, service_type: str, days: Optional[int] = None) -> User:
    tier = TIERS.get(service_type) or ADDONS.get(service_type)
    if not tier:
        raise AuthError(f"Unknown service: {service_type}")
    with session_scope() as session:
        user = session.get(User, _uuid(user_id))
        if not user:
            raise AuthError("User not found")
        now = datetime.now(timezone.utc)
        base = now
        if user.access_expires_at:
            current = user.access_expires_at
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            if current > now:
                base = current
        user.access_tier = service_type
        user.access_expires_at = base + timedelta(days=days or tier.duration_days or 30)
        user.approval_status = "approved"
        session.add(Notification(kind="system", title=f"{user.username} activated", body=f"{tier.label} until {user.access_expires_at:%Y-%m-%d}", user_id=user.id))
        session.flush()
        session.refresh(user)
        return user


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


def _blockscout_transfers(address: str) -> List[Dict[str, Any]]:
    request = urllib.request.Request(BLOCKSCOUT.format(address=address), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode())
    return payload.get("items", [])


def verify_payment(payment_id: str, actor: Optional[str] = None, manual: bool = False) -> Dict[str, Any]:
    """
    Verify a payment claim against the chain.

    ``manual=True`` marks it confirmed without an RPC call (admin override).
    """
    with session_scope() as session:
        payment = session.get(Payment, _uuid(payment_id))
        if not payment:
            raise AuthError("Payment not found")
        if payment.status == "confirmed":
            return {"status": "confirmed", "payment_id": payment.id, "already": True}

        admin_wallet = get_setting(session, "admin_wallet")
        if not admin_wallet:
            raise AuthError("Admin wallet is not configured")

        tx_hash = None
        observed = 0.0
        if not manual:
            try:
                transfers = _blockscout_transfers(admin_wallet)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                return {"status": "unverified", "error": f"chain lookup failed: {exc}"}
            cutoff = datetime.now(timezone.utc) - timedelta(days=3)
            for item in transfers:
                token = item.get("token", {})
                if token.get("symbol", "").upper() != USDC_SYMBOL:
                    continue
                sender = (item.get("from", {}) or {}).get("hash", "").lower()
                receiver = (item.get("to", {}) or {}).get("hash", "").lower()
                if sender != payment.wallet_from.lower() or receiver != admin_wallet.lower():
                    continue
                total = item.get("total", {})
                decimals = int(total.get("decimals") or 6)
                amount = float(total.get("value") or 0) / (10 ** decimals)
                stamp = item.get("timestamp", "")
                try:
                    when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    when = datetime.now(timezone.utc)
                if when < cutoff or amount + 1e-9 < payment.amount_usdc:
                    continue
                tx_hash, observed = item.get("transaction_hash") or item.get("tx_hash"), amount
                break
            if not tx_hash:
                payment.status = "unverified"
                return {"status": "unverified", "error": "no matching USDC transfer found yet"}

        payment.status = "confirmed"
        payment.tx_ref = tx_hash or (f"manual:{actor}" if manual else None)
        payment.confirmed_at = datetime.now(timezone.utc)
        activate_tier(payment.user_id, payment.service_type)
        session.add(Notification(kind="payment", title=f"Payment confirmed: {payment.service_type}", body=f"{payment.amount_usdc} USDC from {payment.wallet_from}", user_id=payment.user_id))
        return {"status": "confirmed", "payment_id": payment.id, "tx": payment.tx_ref, "amount": observed or payment.amount_usdc}


def create_payment(user_id: str, service_type: str, wallet_from: str) -> Payment:
    if not WALLET_RE.match(wallet_from or ""):
        raise AuthError("Sender wallet must be a 0x-prefixed 40-hex address")
    with session_scope() as session:
        admin_wallet = get_setting(session, "admin_wallet")
        if not admin_wallet:
            raise AuthError("Admin wallet is not configured")
        payment = Payment(
            user_id=_uuid(user_id),
            service_type=service_type,
            amount_usdc=tier_price(session, service_type),
            wallet_from=wallet_from,
            wallet_to=admin_wallet,
            status="pending",
        )
        session.add(payment)
        user = session.get(User, _uuid(user_id))
        if user:
            user.wallet_address = wallet_from
        session.flush()
        session.refresh(payment)
        return payment


def payments_for(user_id: str) -> List[Payment]:
    with session_scope() as session:
        return list(session.scalars(select(Payment).where(Payment.user_id == _uuid(user_id)).order_by(Payment.created_at.desc())))


def all_payments() -> List[Payment]:
    with session_scope() as session:
        return list(session.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(200)))


def notifications(unread_only: bool = False) -> List[Notification]:
    with session_scope() as session:
        query = select(Notification).order_by(Notification.created_at.desc()).limit(100)
        if unread_only:
            query = select(Notification).where(Notification.read_at.is_(None)).order_by(Notification.created_at.desc())
        return list(session.scalars(query))


def mark_notifications_read() -> None:
    with session_scope() as session:
        for item in session.scalars(select(Notification).where(Notification.read_at.is_(None))):
            item.read_at = datetime.now(timezone.utc)


__all__ = [
    "AuthError",
    "TIERS",
    "ADDONS",
    "Tier",
    "init_auth_db",
    "needs_setup",
    "create_admin",
    "register_user",
    "authenticate",
    "get_user",
    "approve_user",
    "reject_user",
    "pending_users",
    "all_users",
    "is_active_subscriber",
    "activate_tier",
    "create_payment",
    "verify_payment",
    "payments_for",
    "all_payments",
    "notifications",
    "mark_notifications_read",
    "get_setting",
    "set_setting",
    "tier_price",
    "hash_password",
    "verify_password",
]

def get_setting_safe(key: str, default: str = "") -> str:
    """Read a setting without needing a live session handle."""
    with session_scope() as session:
        return get_setting(session, key, default)
