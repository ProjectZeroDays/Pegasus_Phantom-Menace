"""Contract tests for the fastboot, FRP and root routes."""
import pytest

from pegasus.ui.web.backend.app import create_app


@pytest.fixture()
def client(monkeypatch):
    calls = []

    def fake_run(argv, timeout=15):
        calls.append(argv)
        return {"ok": True, "stdout": "device", "stderr": ""}

    monkeypatch.setattr("pegasus.ui.web.backend.fastboot_routes.run", fake_run)
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    c.calls = calls
    return c


def test_engines(client):
    body = client.get("/api/fastboot/engines").get_json()
    assert len(body["data"]["engines"]) == 9


def test_unlock_ladder(client):
    body = client.post("/api/fastboot/A/unlock").get_json()
    assert body["data"]["steps"]
    assert any("unlock" in s["command"] for s in body["data"]["steps"])


def test_flash_requires_args(client):
    assert client.post("/api/fastboot/A/flash", json={}).status_code == 400


def test_flash_runs(client):
    r = client.post("/api/fastboot/A/flash", json={"partition": "boot", "path": "b.img"})
    assert r.status_code == 200
    assert any("flash" in " ".join(c) for c in client.calls)


def test_getvar(client):
    assert client.get("/api/fastboot/A/getvar?name=all").status_code == 200


def test_slot(client):
    assert client.get("/api/fastboot/A/current-slot").status_code == 200
    assert client.post("/api/fastboot/A/set-active", json={"slot": "b"}).status_code == 200


def test_carrier(client):
    assert client.get("/api/fastboot/A/device-info").status_code == 200
    assert client.post("/api/fastboot/A/carrier-unlock").status_code == 200


def test_erase_and_userdata(client):
    assert client.post("/api/fastboot/A/erase", json={"target": "cache"}).status_code == 200
    assert client.post("/api/fastboot/A/userdata").status_code == 200


def test_root_detect(client):
    assert client.get("/api/fastboot/A/root/detect").get_json()["data"]["solution"] in (
        "magisk", "kernelsu", "apatch", "none")


def test_install_module_requires_path(client):
    assert client.post("/api/fastboot/A/root/install-module", json={}).status_code == 400


def test_samsung_detect(client):
    assert "samsung" in client.get("/api/fastboot/A/samsung/detect").get_json()["data"]


def test_frp_chain_runs(client):
    body = client.post("/api/fastboot/A/frp/chain").get_json()
    assert body["data"]["total"] == 4


def test_play_protect(client):
    assert client.post("/api/fastboot/A/play-protect").get_json()["data"]["total"] == 3


def test_gated(client, monkeypatch):
    monkeypatch.setenv("PEGASUS_REQUIRE_AUTH", "1")
    monkeypatch.setenv("PEGASUS_API_TOKEN", "tok")
    assert client.get("/api/fastboot/engines").status_code == 401
    assert client.get("/api/fastboot/engines",
                      headers={"X-Pegasus-Token": "tok"}).status_code == 200
