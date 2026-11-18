"""Contract tests for the console-facing C2 routes."""
from __future__ import annotations

import pytest

from pegasus.ui.web.backend.app import create_app
from pegasus.ui.web.backend import c2_routes


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_status_reports_bind_default_and_tls(client):
    data = client.get("/api/c2/status").get_json()["data"]
    assert data["running"] is False
    assert data["bind_default"] in ("127.0.0.1", "::1")
    assert "tls" in data


def test_start_rejects_non_numeric_port(client):
    r = client.post("/api/c2/start", json={"port": "http"})
    assert r.status_code == 400
    assert "numeric" in r.get_json()["error"]


def test_start_rejects_out_of_range_port(client):
    assert client.post("/api/c2/start", json={"port": 70000}).status_code == 400


def test_start_rejects_remote_host(client):
    r = client.post("/api/c2/start", json={"port": 0, "host": "203.0.113.9"})
    assert r.status_code == 400
    assert "not a local interface address" in r.get_json()["error"]


def test_start_accepts_loopback_and_reports_bound_port(client):
    body = client.post("/api/c2/start", json={"port": 0, "host": "127.0.0.1"}).get_json()["data"]
    try:
        assert body["started"] is True
        assert body["host"] == "127.0.0.1"
        assert isinstance(body["port"], int) and body["port"] > 0
    finally:
        client.post("/api/c2/stop")


def test_kill_requires_an_identifier(client):
    r = client.post("/api/c2/kill", json={})
    assert r.status_code == 400
    assert "dna or serial" in r.get_json()["error"]


def test_kill_states_the_delivery_limit(client):
    body = client.post("/api/c2/kill", json={"dna": "d" * 16}).get_json()["data"]
    assert body["queued"] is True
    assert "next beacon" in body["note"]


def test_beacon_requires_command(client):
    r = client.post("/api/c2/beacon", json={"dna": "d" * 16})
    assert r.status_code == 400
    assert "command required" in r.get_json()["error"]


def test_resolve_host_rejects_a_typo():
    with pytest.raises(ValueError):
        c2_routes._resolve_host("999.999.999.999")


def test_resolve_host_passes_sentinels():
    for sentinel in ("127.0.0.1", "0.0.0.0", "::1"):
        assert c2_routes._resolve_host(sentinel) == sentinel
    assert c2_routes._resolve_host("") is None
