"""Delivery channel tests: intent construction, audio transcript, send bookkeeping."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest
from pegasus.modules.access_workflow import delivery


class FakeCompleted:
    returncode = 0
    stdout = "Starting: Intent"
    stderr = ""


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def fake_adb(*args, timeout=25):
        calls.append(args)
        return FakeCompleted()

    monkeypatch.setattr(delivery, "adb", fake_adb)
    monkeypatch.setattr(delivery, "first_serial", lambda: "emulator-5554")
    monkeypatch.setattr(delivery, "HISTORY", Path.home() / ".pegasus" / "test_delivery_history.jsonl")
    return calls


def test_channel_catalog_covers_requested_surfaces():
    keys = {channel["key"] for channel in delivery.list_channels()}
    for required in ("sms", "whatsapp", "telegram", "signal", "messenger", "discord", "email", "bluetooth", "nfc", "dialer"):
        assert required in keys


def test_whatsapp_send_builds_package_intent(captured):
    record = delivery.send("whatsapp", "jid@example", "http://10.0.0.2:8080/p.apk", auto_send=False)
    assert record["ok"] is True
    joined = " ".join(captured[0])
    assert "com.whatsapp" in joined
    assert "android.intent.extra.TEXT" in joined
    assert "http://10.0.0.2:8080/p.apk" in joined


def test_email_uses_sendto_and_subject(captured):
    delivery.send("email", "ops@example.com", "http://10.0.0.2:8080/p.apk", auto_send=False)
    joined = " ".join(captured[0])
    assert "android.intent.action.SENDTO" in joined
    assert "mailto:ops@example.com" in joined
    assert "android.intent.extra.SUBJECT" in joined


def test_sms_uses_body_extra(captured):
    delivery.send("sms", "+15551234567", "http://10.0.0.2:8080/p.apk", auto_send=False)
    joined = " ".join(captured[0])
    assert "sms:+15551234567" in joined
    assert "sms_body" in joined


def test_unknown_channel_raises(captured):
    with pytest.raises(delivery.DeliveryError):
        delivery.send("icq", "", "http://x")


def test_transcript_spells_the_url():
    text = delivery.transcript_for("http://192.168.1.5:8080/a.apk")
    assert "dot" in text and "port" in text and "slash" in text


def test_synth_audio_writes_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(delivery, "AUDIO_DIR", tmp_path)
    path = delivery.synth_audio("payload link test", name="t.wav")
    assert path.exists() and path.stat().st_size > 44
    with wave.open(str(path), "rb") as handle:
        assert handle.getnchannels() == 1


def test_server_starts_and_stops():
    info = delivery.start_server(8099)
    assert info["running"] and ":8099" in info["url"]
    stopped = delivery.stop_server()
    assert stopped["running"] is False
