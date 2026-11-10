"""Contract tests for the physical-effect routes."""
import pytest

from pegasus.ui.web.backend.app import create_app


@pytest.fixture()
def client(monkeypatch):
    calls = []

    def fake_run(argv, timeout=15):
        calls.append(argv)
        return {"ok": True, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr("pegasus.ui.web.backend.physical_routes.run", fake_run)
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    c.calls = calls
    return c


def test_engines_lists_groups(client):
    body = client.get("/api/physical/engines").get_json()
    assert body["ok"] is True
    assert len(body["data"]["engines"]) == 8


def test_vibrate_issues_adb(client):
    assert client.post("/api/physical/A/vibrate", json={"ms": 250}).status_code == 200
    assert any("vibrate 250" in " ".join(c) for c in client.calls)


def test_torch_off(client):
    assert client.post("/api/physical/A/torch", json={"on": False}).get_json()["data"]["torch"] == "off"


def test_brightness_clamped(client):
    assert client.post("/api/physical/A/brightness", json={"level": 999}).get_json()["data"]["level"] == 255


def test_volume_clamped(client):
    assert client.post("/api/physical/A/volume", json={"level": -4}).get_json()["data"]["level"] == 0


def test_tts_requires_text(client):
    assert client.post("/api/physical/A/tts", json={}).status_code == 400


def test_input_text(client):
    assert client.post("/api/physical/A/input/text", json={"text": "hi"}).status_code == 200


def test_tap_and_swipe(client):
    assert client.post("/api/physical/A/input/tap", json={"x": 5, "y": 9}).status_code == 200
    assert client.post("/api/physical/A/input/swipe", json={"x1": 0, "y1": 0,
                                                            "x2": 9, "y2": 9}).status_code == 200


def test_radios(client):
    for name in ("wifi", "bluetooth", "gps", "airplane"):
        assert client.post("/api/physical/A/%s" % name, json={"on": True}).status_code == 200


def test_power(client):
    for name in ("wake", "sleep", "lock", "unlock"):
        assert client.post("/api/physical/A/%s" % name).status_code == 200


def test_state_reads(client):
    assert "battery" in client.get("/api/physical/A/state").get_json()["data"]


def test_gated_when_flag_on(client, monkeypatch):
    monkeypatch.setenv("PEGASUS_REQUIRE_AUTH", "1")
    monkeypatch.setenv("PEGASUS_API_TOKEN", "tok")
    assert client.post("/api/physical/A/vibrate").status_code == 401
    assert client.post("/api/physical/A/vibrate",
                       headers={"X-Pegasus-Token": "tok"}).status_code == 200
