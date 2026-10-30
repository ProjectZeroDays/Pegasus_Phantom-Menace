"""Dashboard routes, redaction, delivery API and admin controls."""

from __future__ import annotations

import re
import uuid

import pytest
from pegasus.modules.access_workflow import auth
from pegasus.modules.access_workflow.dashboard_server import app


def csrf(client, path="/login"):
    match = re.search(r'name="csrf" value="([^"]+)"', client.get(path).text)
    return match.group(1) if match else ""


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def admin(client):
    if auth.needs_setup():
        token = csrf(client, "/setup")
        client.post("/setup", data={
            "csrf": token, "username": "admin", "email": "admin@test.local",
            "password": "secret1", "passkey": "longpasskey1",
            "wallet": "0x1111111111111111111111111111111111111111",
        })
    token = csrf(client)
    client.post("/login", data={"csrf": token, "username": "admin", "password": "secret1", "passkey": "longpasskey1"})
    return client


def test_guest_landing_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Deploy a carrier" in response.data
    assert b"Guest view" in response.data


def test_guest_exploit_run_is_redacted(client):
    response = client.post("/api/exploits/run", json={"key": "android_bluetooth"})
    assert response.status_code == 200
    assert "summary" in response.get_json()


def test_admin_sees_exploit_internals(admin):
    response = admin.post("/api/exploits/run", json={"key": "android_bluetooth"})
    body = response.get_json()
    assert response.status_code == 200
    assert "summary" not in body


def test_delivery_channels_exposed(admin):
    response = admin.get("/api/delivery/channels")
    assert response.status_code == 200
    assert len(response.get_json()["channels"]) >= 15


def test_catalog_lists_vectors(admin):
    response = admin.get("/api/catalog?category=messaging")
    assert response.status_code == 200
    vectors = response.get_json()["vectors"]
    assert vectors and all(item["category"] == "messaging" for item in vectors)


def test_command_endpoint_runs(admin):
    token = admin.get("/").text
    match = re.search(r'name="csrf" content="([^"]+)"', token)
    headers = {"X-CSRF-Token": match.group(1)} if match else {}
    response = admin.post("/api/command", json={"name": "passgen", "args": ["14"]}, headers=headers)
    assert response.status_code == 200
    assert response.get_json()["result"]["length"] == 14


def test_admin_user_controls(admin):
    suffix = uuid.uuid4().hex[:8]
    user = auth.register_user(f"ctl{suffix}", f"ctl{suffix}@test.local", "pass1")
    assert admin.post(f"/api/admin/approve/{user.id}").status_code == 200
    assert admin.post(f"/api/admin/users/{user.id}/tier", json={"tier": "monthly"}).status_code == 200
    assert auth.get_user(str(user.id)).access_tier == "monthly"
    assert admin.post(f"/api/admin/users/{user.id}/active").status_code == 200
    assert admin.post(f"/api/admin/users/{user.id}/passkey").status_code == 200
    assert admin.post(f"/api/admin/users/{user.id}/wallet", json={"wallet": "0x4444444444444444444444444444444444444444"}).status_code == 200
    assert admin.delete(f"/api/admin/users/{user.id}").status_code == 200


def test_admin_system_snapshot(admin):
    response = admin.get("/api/admin/system")
    assert response.status_code == 200
    body = response.get_json()
    assert "daemon" in body and "disk" in body and "parity" in body


def test_payment_gate_for_new_user(client):
    suffix = uuid.uuid4().hex[:8]
    token = csrf(client, "/register")
    client.post("/register", data={"csrf": token, "username": f"pay{suffix}", "email": f"p{suffix}@test.local", "password": "pass1"})
    user = next(item for item in auth.pending_users() if item.username == f"pay{suffix}")
    auth.approve_user(str(user.id))
    login_token = csrf(client)
    client.post("/login", data={"csrf": login_token, "username": user.username, "password": "pass1"})
    assert client.get("/api/devices").status_code == 200
    assert client.get("/payment").status_code == 200
    auth.admin_delete_user(str(user.id))
