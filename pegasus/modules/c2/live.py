"""Live capture helpers."""
import pathlib
import subprocess

ADB = "adb"


def _run(serial: str, *args: str, timeout: int = 60) -> tuple[int, str]:
    p = subprocess.run([ADB, "-s", serial, "shell", *args], capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def mic(serial: str, seconds: int, out: pathlib.Path) -> pathlib.Path:
    remote = f"/sdcard/.pcm_{seconds}.wav"
    _run(serial, f"timeout {seconds} screenrecord --audio /dev/null {remote}")
    subprocess.run([ADB, "-s", serial, "pull", remote, str(out)], timeout=120)
    return out


def camera(serial: str, out: pathlib.Path) -> pathlib.Path:
    remote = "/sdcard/DCIM/.snap.jpg"
    _run(serial, "am", "start", "-a", "android.media.action.STILL_IMAGE_CAMERA")
    _run(serial, "input", "keyevent", "27")
    subprocess.run([ADB, "-s", serial, "pull", remote, str(out)], timeout=60)
    return out


def screen(serial: str, out: pathlib.Path) -> pathlib.Path:
    remote = "/sdcard/.scr.png"
    _run(serial, f"screencap -p {remote}")
    subprocess.run([ADB, "-s", serial, "pull", remote, str(out)], timeout=60)
    return out
