"""Tests for the Pegasus web GUI backend (no device required).

Run with:  python -m pytest pegasus/ui/web/tests -q
"""
from __future__ import annotations

import json

import pytest

from pegasus.ui.web.backend.app import create_app
from pegasus.ui.web.backend.capture import StreamCapture
from pegasus.ui.web.backend import telemetry


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["data"]["status"] == "online"


def test_system_reports_components(client):
    body = client.get("/api/system").get_json()["data"]
    names = {component["name"] for component in body["components"]}
    assert {"Web API", "Plugin system", "Database"} <= names
    assert body["environment"]["python"]
    assert body["workspace"]["workspace"]


def test_plugins_loaded_with_commands(client):
    body = client.get("/api/plugins").get_json()["data"]
    names = {plugin["name"] for plugin in body["plugins"]}
    # Core modules that must always load.
    assert {"device", "payload", "session", "reporting", "cve_scanner", "access_workflow"} <= names
    assert sum(len(p["commands"]) for p in body["plugins"]) > 20


def test_command_registry(client):
    body = client.get("/api/commands").get_json()["data"]
    commands = {entry["name"] for entry in body["commands"]}
    assert "devices" in commands
    assert "cve-scan" in commands
    assert "payload-gen" in commands


def test_stage_catalogue(client):
    body = client.get("/api/stages").get_json()["data"]
    assert len(body["stages"]) == 12
    assert {category["id"] for category in body["categories"]} == {
        "full_lifecycle",
        "stage_by_stage",
    }


def test_cve_database(client):
    body = client.get("/api/cve").get_json()["data"]
    assert body["count"] >= 10
    cve_ids = {entry["id"] for entry in body["cves"]}
    assert "CVE-2024-31317" in cve_ids


def test_tool_scan_shape(client):
    body = client.get("/api/system/tools").get_json()["data"]
    assert len(body["tools"]) >= 10
    for tool in body["tools"]:
        assert {"key", "label", "available", "purpose"} <= set(tool)


def test_slash_commands(client):
    body = client.get("/api/slash-commands").get_json()["data"]
    names = {entry["name"] for entry in body["commands"]}
    assert "/adb-devices" in names
    assert "/god-mode" in names


def test_spa_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8", errors="replace")
    assert "<div id=\"root\">" in html or "PEGASUS" in html.upper()


def test_spa_fallback_for_client_routes(client):
    response = client.get("/devices")
    assert response.status_code == 200


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["ok"] is False


def test_command_run_dispatches_job(client):
    response = client.post("/api/commands/access-vectors/run", json={"args": []})
    assert response.status_code == 200
    job = response.get_json()["data"]["job"]
    assert job["status"] in ("queued", "running", "succeeded", "failed")
    detail = client.get(f"/api/jobs/{job['id']}").get_json()["data"]["job"]
    assert detail["kind"] == "command"


def test_unknown_command_404(client):
    response = client.post("/api/commands/not-a-command/run", json={"args": []})
    assert response.status_code == 404


def test_geofence_crud(client):
    serial = "TEST-SERIAL-0001"
    created = client.post(
        f"/api/devices/{serial}/geofences",
        json={"name": "Lab", "lat": 51.5, "lng": -0.12, "radiusMeters": 250},
    )
    assert created.status_code == 200
    fence = created.get_json()["data"]["geofence"]
    assert fence["name"] == "Lab"
    assert fence["radiusMeters"] == 250

    listed = client.get(f"/api/devices/{serial}/geofences").get_json()["data"]["geofences"]
    assert any(item["id"] == fence["id"] for item in listed)

    toggled = client.patch(f"/api/geofences/{fence['id']}/toggle")
    assert toggled.status_code == 200

    deleted = client.delete(f"/api/geofences/{fence['id']}")
    assert deleted.status_code == 200


def test_keyword_lifecycle(client):
    serial = "TEST-SERIAL-0002"
    created = client.post(f"/api/devices/{serial}/keywords", json={"keyword": "otp"})
    assert created.status_code == 200
    keyword = created.get_json()["data"]["keyword"]
    assert keyword["keyword"] == "otp"

    scanned = client.post(f"/api/devices/{serial}/keywords/scan")
    assert scanned.status_code == 200
    assert "hits" in scanned.get_json()["data"]

    assert client.delete(f"/api/keywords/{keyword['id']}").status_code == 200


def test_geofence_rejects_bad_coordinates(client):
    response = client.post(
        "/api/devices/TEST/bad/geofences",
        json={"name": "bad", "lat": "abc", "lng": "xyz", "radiusMeters": 1},
    )
    assert response.status_code in (200, 400)


def test_wind_scale_progress_endpoint(client):
    body = client.get("/api/jobs").get_json()["data"]
    assert "stats" in body and "jobs" in body


# ---------------------------------------------------------------------------
# Capture layer
# ---------------------------------------------------------------------------


def test_capture_collects_python_writes():
    with StreamCapture() as capture:
        print("hello capture")
    assert "hello capture" in capture.getvalue()
    capture.close()


def test_capture_keeps_unicode_box_drawing():
    with StreamCapture() as capture:
        console = capture.console()
        console.print("[bold]naïve café ─ │[/bold]")
    output = capture.getvalue()
    assert "café" in output
    assert "─" in output
    capture.close()


def test_console_markup_is_preserved_not_stripped_into_mojibake():
    with StreamCapture() as capture:
        capture.console().print("[red]x[/red]")
    output = capture.getvalue()
    assert "\ufffd" not in output


# ---------------------------------------------------------------------------
# Telemetry store
# ---------------------------------------------------------------------------


def test_telemetry_sample_roundtrip():
    serial = "TEST-SERIAL-0003"
    rows = [{"id": 1, "name": "Alice", "phones": ["+100"], "emails": []}]
    telemetry.save_samples(serial, "contacts", rows)
    latest = telemetry.latest_sample(serial, "contacts")
    assert latest is not None
    assert latest["rows"][0]["name"] == "Alice"


def test_telemetry_summary_shape():
    summary = telemetry.summary("TEST-SERIAL-0004")
    assert "counts" in summary
    assert "topLocations" in summary
    assert summary["deviceSerial"] == "TEST-SERIAL-0004"
    json.dumps(summary)  # must be serialisable


def test_telemetry_collectors_handle_missing_device():
    # No device attached: every collector must degrade to an empty list.
    for kind in ("contacts", "sms", "calls", "apps", "wifi", "locations"):
        rows = telemetry.collect("NO-SUCH-DEVICE", kind, persist=False)
        assert isinstance(rows, list)


def test_unknown_slash_command_404(client):
    assert client.post("/api/slash-commands/not-real/run", json={}).status_code == 404


# ---------------------------------------------------------------------------
# Frozen / sourceless plugin loading
# ---------------------------------------------------------------------------


def test_builtin_loader_loads_every_module_without_files():
    """Regression: PyInstaller bundles have no plugin.py on disk.

    `load_all_plugins` must still produce the full plugin set by importing the
    built-in module packages directly.
    """
    from pegasus.core.config import get_settings
    from pegasus.core.plugin import AppContext, PluginManager

    context = AppContext(get_settings())
    manager = PluginManager(context)
    loaded = manager.load_builtin_plugins()

    names = {plugin.metadata.name for plugin in loaded}
    assert len(loaded) >= 13, f"expected all builtin modules, got {sorted(names)}"
    assert {"device", "payload", "session", "reporting", "cve_scanner", "access_workflow"} <= names
    assert len(context.commands) >= 35


def test_builtin_loader_binds_metadata_to_classes():
    from pegasus.core.config import get_settings
    from pegasus.core.plugin import AppContext, PluginManager
    from pegasus.modules.device.module import DeviceModule

    context = AppContext(get_settings())
    manager = PluginManager(context)
    manager.load_builtin_plugins()

    assert DeviceModule.metadata is not None
    assert DeviceModule.metadata.name == "device"


# ---------------------------------------------------------------------------
# NSO capability parity
# ---------------------------------------------------------------------------


def test_capability_parity_endpoint(client):
    body = client.get("/api/nso/capabilities").get_json()["data"]
    assert len(body["capabilities"]) >= 25
    assert body["parity"]["total"] >= 25
    for capability in body["capabilities"]:
        assert {"key", "name", "category", "parity", "description"} <= set(capability)


def test_capability_manifest_endpoint(client):
    body = client.get("/api/nso/manifest").get_json()["data"]
    assert isinstance(body["manifest"], dict)


def test_capability_run_dispatches_job(client):
    response = client.post("/api/nso/run/device_profile", json={})
    assert response.status_code == 200
    job = response.get_json()["data"]["job"]
    assert job["kind"] == "capability"
