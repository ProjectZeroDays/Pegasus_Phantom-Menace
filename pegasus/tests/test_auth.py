"""Auth primitives, approval flow and tier activation."""

from __future__ import annotations

import uuid

import pytest
from pegasus.modules.access_workflow import auth


def test_password_roundtrip():
    stored = auth.hash_password("secret1")
    assert auth.verify_password("secret1", stored)
    assert not auth.verify_password("wrong", stored)


def test_passkey_roundtrip():
    stored = auth.hash_passkey("long-passkey")
    assert auth.verify_passkey("long-passkey", stored)
    assert not auth.verify_passkey("nope", stored)


def test_demo_account_seeded():
    user = auth.authenticate("demo", "demo")
    assert user.is_demo and auth.is_active_subscriber(user)


def test_registration_approval_and_activation():
    suffix = uuid.uuid4().hex[:8]
    user = auth.register_user(f"user{suffix}", f"{suffix}@example.test", "pass1", "0x3333333333333333333333333333333333333333")
    assert user.approval_status == "pending"
    assert any(item.username == user.username for item in auth.pending_users())
    auth.approve_user(str(user.id))
    assert auth.get_user(str(user.id)).approval_status == "approved"
    auth.admin_set_tier(str(user.id), "weekly")
    refreshed = auth.get_user(str(user.id))
    assert refreshed.access_tier == "weekly"
    assert auth.is_active_subscriber(refreshed)
    auth.admin_delete_user(str(user.id))


def test_unknown_tier_rejected():
    with pytest.raises(auth.AuthError):
        auth.activate_tier(str(auth.authenticate("demo", "demo").id), "decade")


def test_admin_reset_passkey_changes_secret():
    suffix = uuid.uuid4().hex[:8]
    user = auth.register_user(f"key{suffix}", f"k{suffix}@example.test", "pass1")
    temp = auth.admin_reset_passkey(str(user.id))
    refreshed = auth.get_user(str(user.id))
    assert auth.verify_passkey(temp, refreshed.passkey_hash)
    auth.admin_delete_user(str(user.id))
