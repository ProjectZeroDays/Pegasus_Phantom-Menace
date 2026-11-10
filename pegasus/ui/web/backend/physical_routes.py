"""Physical-effect routes: vibration, torch, display, audio, radio, input.

Each effect maps to a primary command with one documented fallback; the first
that exits cleanly wins and the response reports which one ran. Views are
phys_-prefixed so endpoint names never collide with app.py.
"""
from __future__ import annotations

import os
import shlex

from flask import request, session

from pegasus.ui.web.backend.tools import run

AUTH_FLAG = "PEGASUS_REQUIRE_AUTH"
AUTH_TOKEN = "PEGASUS_API_TOKEN"


def _auth_on() -> bool:
    return os.environ.get(AUTH_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _require_token(view):
    import functools

    @functools.wraps(view)
    def wrapper(*a, **k):
        if not _auth_on():
            return view(*a, **k)
        expected = os.environ.get(AUTH_TOKEN, "").strip()
        supplied = (
            request.headers.get("X-Pegasus-Token")
            or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            or request.args.get("token")
            or ""
        ).strip()
        if expected and supplied == expected:
            return view(*a, **k)
        if session.get("pegasus_user") or session.get("user"):
            return view(*a, **k)
        return {"ok": False, "error": "unauthorized"}, 401

    return wrapper


def _sh(serial: str, command: str, timeout: int = 15) -> dict:
    return run(["adb", "-s", serial, "shell", command], timeout=timeout)


def _first_ok(serial: str, candidates: list, timeout: int = 15) -> dict:
    """Run candidates in order; return the first clean result."""
    tried = []
    for command in candidates:
        result = _sh(serial, command, timeout=timeout)
        tried.append(command)
        if result.get("ok"):
            result["command"] = command
            result["tried"] = tried
            return result
    return {"ok": False, "stdout": "", "stderr": "all candidates failed", "tried": tried}


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def register(app, ok, fail) -> None:  # noqa: ANN001
    @app.get("/api/physical/engines")
    @_require_token
    def phys_engines():
        return ok({"engines": [
            {"key": "haptic", "label": "Haptics", "effects": ["vibrate"]},
            {"key": "display", "label": "Display",
             "effects": ["torch", "brightness", "screen", "rotate"]},
            {"key": "audio", "label": "Audio",
             "effects": ["volume", "ringer", "media", "tts", "beep"]},
            {"key": "radio", "label": "Radios",
             "effects": ["airplane", "wifi", "bluetooth", "gps"]},
            {"key": "input", "label": "Input", "effects": ["text", "key", "tap", "swipe"]},
            {"key": "power", "label": "Power",
             "effects": ["wake", "sleep", "lock", "unlock", "reboot"]},
            {"key": "sensor", "label": "Sensors", "effects": ["state", "thermal", "sensors"]},
            {"key": "capture", "label": "Capture", "effects": ["screenshot", "record"]},
        ]})

    @app.get("/api/physical/<string:serial>/state")
    @_require_token
    def phys_state(serial):
        readings = {}
        for key, command in (
            ("battery", "dumpsys battery"),
            ("thermal", "dumpsys thermalservice"),
            ("brightness", "settings get system screen_brightness"),
            ("ringer", "settings get global zen_mode"),
        ):
            result = _sh(serial, command)
            readings[key] = result.get("stdout", "").strip()[:2000] if result.get("ok") else None
        return ok(readings)

    @app.get("/api/physical/<string:serial>/thermal")
    @_require_token
    def phys_thermal(serial):
        result = _first_ok(serial, ["dumpsys thermalservice",
                                    "cat /sys/class/thermal/thermal_zone0/temp"])
        return ok({"raw": result.get("stdout", "").strip()[:4000], "ok": result.get("ok", False)})

    @app.get("/api/physical/<string:serial>/sensors")
    @_require_token
    def phys_sensors(serial):
        result = _first_ok(serial, ["dumpsys sensorservice", "ls /sys/class/sensors"])
        return ok({"raw": result.get("stdout", "").strip()[:6000], "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/vibrate")
    @_require_token
    def phys_vibrate(serial):
        ms = int(_payload().get("ms") or 400)
        result = _first_ok(serial, ["cmd vibrator vibrate %d" % ms,
                                    "service call vibrator 2 i32 1 i32 %d" % ms])
        return ok({"ms": ms, "ok": result.get("ok", False), "command": result.get("command")})

    @app.post("/api/physical/<string:serial>/torch")
    @_require_token
    def phys_torch(serial):
        state = "on" if _payload().get("on", True) else "off"
        result = _first_ok(serial, ["cmd flashlight %s" % state,
                                    "settings put system torch_state %d" % (1 if state == "on" else 0)])
        return ok({"torch": state, "ok": result.get("ok", False), "command": result.get("command")})

    @app.post("/api/physical/<string:serial>/brightness")
    @_require_token
    def phys_brightness(serial):
        level = max(0, min(255, int(_payload().get("level") or 128)))
        result = _first_ok(serial, ["settings put system screen_brightness %d" % level,
                                    "settings put system screen_brightness_mode 0"])
        return ok({"level": level, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/rotate")
    @_require_token
    def phys_rotate(serial):
        rotation = max(0, min(3, int(_payload().get("rotation") or 0)))
        _sh(serial, "settings put system accelerometer_rotation 0")
        result = _sh(serial, "settings put system user_rotation %d" % rotation)
        return ok({"rotation": rotation, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/screen")
    @_require_token
    def phys_screen(serial):
        action = (_payload().get("action") or "toggle").lower()
        key = {"on": 224, "off": 223, "toggle": 26}.get(action, 26)
        result = _sh(serial, "input keyevent %d" % key)
        return ok({"action": action, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/volume")
    @_require_token
    def phys_volume(serial):
        body = _payload()
        stream = str(body.get("stream") or 3)
        level = max(0, min(15, int(body.get("level") or 7)))
        result = _sh(serial, "media volume --stream %s --set %d" % (stream, level))
        return ok({"stream": stream, "level": level, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/ringer")
    @_require_token
    def phys_ringer(serial):
        mode = max(0, min(3, int(_payload().get("mode") or 0)))
        result = _first_ok(serial, ["cmd audio set-ringer-mode %d" % mode,
                                    "settings put global zen_mode %d" % mode])
        return ok({"mode": mode, "ok": result.get("ok", False), "command": result.get("command")})

    @app.post("/api/physical/<string:serial>/media")
    @_require_token
    def phys_media(serial):
        action = (_payload().get("action") or "playpause").lower()
        key = {"playpause": 85, "play": 126, "pause": 127, "next": 87,
               "prev": 88, "stop": 86}.get(action, 85)
        result = _sh(serial, "input keyevent %d" % key)
        return ok({"action": action, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/tts")
    @_require_token
    def phys_tts(serial):
        text = str(_payload().get("text") or "").strip()
        if not text:
            return fail("text required", 400)
        quoted = shlex.quote(text)
        result = _first_ok(serial, ["cmd text-to-speech speak %s" % quoted,
                                    "termux-tts-speak %s" % quoted])
        return ok({"text": text, "ok": result.get("ok", False), "command": result.get("command")})

    @app.post("/api/physical/<string:serial>/beep")
    @_require_token
    def phys_beep(serial):
        hz = max(100, min(8000, int(_payload().get("hz") or 880)))
        result = _first_ok(serial, ["cmd audio beep %d" % hz, "tone %d" % hz])
        return ok({"hz": hz, "ok": result.get("ok", False), "command": result.get("command")})

    def _radio(serial, on, on_cmd, off_cmd):
        result = _first_ok(serial, [on_cmd if on else off_cmd])
        return {"state": "on" if on else "off", "ok": result.get("ok", False),
                "command": result.get("command")}

    @app.post("/api/physical/<string:serial>/airplane")
    @_require_token
    def phys_airplane(serial):
        on = bool(_payload().get("on", True))
        result = _first_ok(serial, ["cmd connectivity airplane-mode %s"
                                    % ("enable" if on else "disable")])
        return ok({"airplane": on, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/wifi")
    @_require_token
    def phys_wifi(serial):
        return ok(_radio(serial, bool(_payload().get("on", True)),
                         "svc wifi enable", "svc wifi disable"))

    @app.post("/api/physical/<string:serial>/bluetooth")
    @_require_token
    def phys_bluetooth(serial):
        return ok(_radio(serial, bool(_payload().get("on", True)),
                         "svc bluetooth enable", "svc bluetooth disable"))

    @app.post("/api/physical/<string:serial>/gps")
    @_require_token
    def phys_gps(serial):
        on = bool(_payload().get("on", True))
        result = _sh(serial, "settings put secure location_mode %d" % (3 if on else 0))
        return ok({"gps": on, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/input/text")
    @_require_token
    def phys_input_text(serial):
        text = str(_payload().get("text") or "")
        if not text:
            return fail("text required", 400)
        result = _sh(serial, "input text %s" % shlex.quote(text))
        return ok({"text": text, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/input/key")
    @_require_token
    def phys_input_key(serial):
        key = int(_payload().get("key") or 3)
        result = _sh(serial, "input keyevent %d" % key)
        return ok({"key": key, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/input/tap")
    @_require_token
    def phys_input_tap(serial):
        body = _payload()
        x, y = int(body.get("x") or 0), int(body.get("y") or 0)
        result = _sh(serial, "input tap %d %d" % (x, y))
        return ok({"x": x, "y": y, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/input/swipe")
    @_require_token
    def phys_input_swipe(serial):
        body = _payload()
        x1, y1 = int(body.get("x1") or 0), int(body.get("y1") or 0)
        x2, y2 = int(body.get("x2") or 0), int(body.get("y2") or 0)
        ms = int(body.get("ms") or 300)
        result = _sh(serial, "input swipe %d %d %d %d %d" % (x1, y1, x2, y2, ms))
        return ok({"from": [x1, y1], "to": [x2, y2], "ms": ms, "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/wake")
    @_require_token
    def phys_wake(serial):
        return ok({"ok": _sh(serial, "input keyevent 224").get("ok", False)})

    @app.post("/api/physical/<string:serial>/sleep")
    @_require_token
    def phys_sleep(serial):
        return ok({"ok": _sh(serial, "input keyevent 223").get("ok", False)})

    @app.post("/api/physical/<string:serial>/lock")
    @_require_token
    def phys_lock(serial):
        return ok({"ok": _sh(serial, "input keyevent 26").get("ok", False)})

    @app.post("/api/physical/<string:serial>/unlock")
    @_require_token
    def phys_unlock(serial):
        _sh(serial, "input keyevent 224")
        return ok({"ok": _sh(serial, "input keyevent 82").get("ok", False)})

    @app.post("/api/physical/<string:serial>/reboot")
    @_require_token
    def phys_reboot(serial):
        mode = str(_payload().get("mode") or "").strip()
        result = _sh(serial, "reboot %s" % mode if mode else "reboot", timeout=30)
        return ok({"mode": mode or "system", "ok": result.get("ok", False)})

    @app.post("/api/physical/<string:serial>/screenshot")
    @_require_token
    def phys_screenshot(serial):
        result = run(["adb", "-s", serial, "exec-out", "screencap", "-p"], timeout=40)
        if not result.get("ok"):
            return fail("screencap failed", 500)
        return ok({"bytes": len(result.get("stdout", ""))})

    @app.post("/api/physical/<string:serial>/record")
    @_require_token
    def phys_record(serial):
        action = (_payload().get("action") or "start").lower()
        remote = "/sdcard/pegasus-phys.mp4"
        if action == "stop":
            result = _sh(serial, "pkill -f screenrecord")
            return ok({"recording": False, "ok": result.get("ok", False)})
        result = _sh(serial, "screenrecord --time-limit 180 %s &" % remote)
        return ok({"recording": True, "path": remote, "ok": result.get("ok", False)})
