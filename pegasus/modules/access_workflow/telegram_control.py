"""
Pegasus Phantom Menace v2 - Telegram Remote Control

Drives a Pegasus host from Telegram over the Bot API, with no third-party
client library: long polling, command dispatch and file uploads all go through
``urllib``.

Supported commands (from the authorised chat only):

    /help           command list
    /status         host, uptime, adb state
    /devices        connected ADB devices
    /shell <cmd>    run a shell command on the host
    /screenshot     screencap the first device and send it
    /notify <text>  broadcast a one-line message to the chat

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

API = "https://api.telegram.org/bot{token}/{method}"
CONFIG_PATH = Path.home() / ".pegasus" / "telegram_config.json"
SHELL_TIMEOUT = 45
POLL_TIMEOUT = 30


class TelegramError(RuntimeError):
    """Raised for configuration or transport failures."""


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_config(token: str, chat_id: str) -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"token": token, "chat_id": chat_id}, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
    return CONFIG_PATH


def _call(token: str, method: str, request_timeout: int = 20, **params: Any) -> Dict[str, Any]:
    body = None
    url = API.format(token=token, method=method)
    if params:
        body = json.dumps(params).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise TelegramError(f"{method} HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, socket.timeout) as exc:
        raise TelegramError(f"{method} transport error: {exc}") from exc
    if not payload.get("ok"):
        raise TelegramError(f"{method}: {payload.get('description', 'unknown error')}")
    return payload.get("result", {})


def send_message(text: str, token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
    config = load_config()
    token = token or config.get("token", "")
    chat_id = chat_id or config.get("chat_id", "")
    if not token or not chat_id:
        raise TelegramError("Telegram is not configured (run setup)")
    return _call(token, "sendMessage", chat_id=chat_id, text=text[:4000], disable_web_page_preview=True)


def send_photo(path: str | Path, caption: str = "", token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
    config = load_config()
    token = token or config.get("token", "")
    chat_id = chat_id or config.get("chat_id", "")
    if not token or not chat_id:
        raise TelegramError("Telegram is not configured (run setup)")

    file = Path(path)
    if not file.exists():
        raise TelegramError(f"Photo not found: {file}")

    boundary = "----PegasusBoundary"
    parts: List[bytes] = []
    for name, value in (("chat_id", chat_id), ("caption", caption)):
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{file.name}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n".encode()
    )
    parts.append(file.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        API.format(token=token, method="sendPhoto"),
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    if not payload.get("ok"):
        raise TelegramError(payload.get("description", "sendPhoto failed"))
    return payload.get("result", {})


def setup(token: str, chat_id: str) -> Dict[str, Any]:
    """Validate a bot token, discover the chat when omitted, and persist."""
    bot = _call(token, "getMe")
    if not chat_id:
        updates = _call(token, "getUpdates", timeout=10)
        for update in reversed(updates):
            message = update.get("message") or {}
            if message.get("chat", {}).get("id"):
                chat_id = str(message["chat"]["id"])
                break
    if not chat_id:
        raise TelegramError("Could not discover chat_id; message the bot once then retry")
    save_config(token, chat_id)
    send_message("Pegasus remote control connected. Send /help.", token=token, chat_id=chat_id)
    return {"bot": bot.get("username"), "chat_id": chat_id}


# ---------------------------------------------------------------------------
# Remote control loop
# ---------------------------------------------------------------------------


def _adb(*args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)


def _host_status() -> str:
    uptime = time.time() - START_TIME
    hours, remainder = divmod(int(uptime), 3600)
    minutes, seconds = divmod(remainder, 60)
    try:
        devices = [line for line in _adb("devices").stdout.splitlines()[1:] if line.strip()]
        adb_state = f"{len(devices)} device(s)"
    except (OSError, subprocess.TimeoutExpired):
        adb_state = "adb unavailable"
    return (
        f"host: {platform.node()}\nplatform: {platform.system()} {platform.release()}\n"
        f"uptime: {hours:02d}:{minutes:02d}:{seconds:02d}\nadb: {adb_state}"
    )


HELP = (
    "/help - this list\n"
    "/status - host and ADB state\n"
    "/devices - connected devices\n"
    "/shell <cmd> - run on host\n"
    "/screenshot - capture first device\n"
    "/notify <text> - echo to chat"
)

START_TIME = time.time()
_handlers: Dict[str, Callable[[str], Optional[str]]] = {}


def _handle_shell(argument: str) -> str:
    if not argument:
        return "usage: /shell <cmd>"
    try:
        proc = subprocess.run(argument, shell=True, capture_output=True, text=True, timeout=SHELL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"timed out after {SHELL_TIMEOUT}s"
    output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return f"exit {proc.returncode}\n{output.strip()[:3500] or '(no output)'}"


def _handle_devices(_: str) -> str:
    try:
        return _adb("devices").stdout.strip() or "no devices"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"adb error: {exc}"


def _handle_screenshot(_: str) -> Optional[str]:
    try:
        devices = [line.split()[0] for line in _adb("devices").stdout.splitlines()[1:] if line.strip()]
        if not devices:
            return "no device connected"
        target = Path.home() / ".pegasus" / "screenshots"
        target.mkdir(parents=True, exist_ok=True)
        shot = target / f"remote_{int(time.time())}.png"
        with shot.open("wb") as handle:
            proc = subprocess.run(
                ["adb", "-s", devices[0], "exec-out", "screencap", "-p"],
                stdout=handle, stderr=subprocess.PIPE, timeout=30,
            )
        if proc.returncode != 0:
            return f"screencap failed: {proc.stderr.decode(errors='replace')[:200]}"
        config = load_config()
        send_photo(shot, caption=devices[0], token=config.get("token"), chat_id=config.get("chat_id"))
        return None
    except (OSError, subprocess.TimeoutExpired, TelegramError) as exc:
        return f"screenshot error: {exc}"


_handlers.update(
    {
        "/help": lambda _: HELP,
        "/start": lambda _: HELP,
        "/status": lambda _: _host_status(),
        "/devices": _handle_devices,
        "/shell": _handle_shell,
        "/screenshot": _handle_screenshot,
        "/notify": lambda argument: argument or "usage: /notify <text>",
    }
)


class TelegramBot:
    """Background long-polling worker."""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = str(chat_id)
        self.offset = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.seen = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="pegasus-telegram", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _dispatch(self, text: str) -> None:
        command, _, argument = text.partition(" ")
        handler = _handlers.get(command.split("@")[0].lower())
        try:
            reply = handler(argument.strip()) if handler else f"unknown command: {command}\n\n{HELP}"
        except Exception as exc:  # keep the loop alive
            reply = f"error: {exc}"
        if reply:
            try:
                send_message(reply, token=self.token, chat_id=self.chat_id)
            except TelegramError:
                pass

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                updates = _call(self.token, "getUpdates", request_timeout=POLL_TIMEOUT, offset=self.offset, timeout=POLL_TIMEOUT)
            except TelegramError:
                self._stop.wait(5)
                continue
            for update in updates:
                self.offset = update.get("update_id", self.offset) + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                if str(message.get("chat", {}).get("id")) != self.chat_id:
                    continue
                text = (message.get("text") or "").strip()
                if not text.startswith("/"):
                    continue
                self.seen += 1
                self._dispatch(text)

    def info(self) -> Dict[str, Any]:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "chat_id": self.chat_id,
            "commands_seen": self.seen,
        }


_bot: Optional[TelegramBot] = None


def start_bot(token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Start (or restart) the remote-control worker."""
    global _bot
    config = load_config()
    token = token or config.get("token", "")
    chat_id = chat_id or config.get("chat_id", "")
    if not token or not chat_id:
        raise TelegramError("Telegram is not configured (run setup)")
    if _bot:
        _bot.stop()
    _bot = TelegramBot(token, chat_id)
    _bot.start()
    return _bot.info()


def stop_bot() -> bool:
    global _bot
    if _bot:
        _bot.stop()
        _bot = None
        return True
    return False


def bot_info() -> Dict[str, Any]:
    return _bot.info() if _bot else {"running": False}


__all__ = [
    "TelegramError",
    "TelegramBot",
    "load_config",
    "save_config",
    "setup",
    "send_message",
    "send_photo",
    "start_bot",
    "stop_bot",
    "bot_info",
]
