"""Shred, scrub timestamps, clear residue."""
import subprocess

ADB = "adb"
SCRUB = "find {root} -newermt '{start}' -exec touch -d '{old}' {{}} \\; 2>/dev/null"


def _shell(serial: str, cmd: str, timeout: int = 120) -> str:
    p = subprocess.run([ADB, "-s", serial, "shell", cmd], capture_output=True,
                       text=True, timeout=timeout)
    return p.stdout + p.stderr


def shred(serial: str, paths: list[str]) -> list[str]:
    for path in paths:
        _shell(serial, f"shred -u -z -n 3 '{path}' 2>/dev/null || rm -f '{path}'")
    return paths


def scrub_times(serial: str, root: str, start: str, old: str) -> str:
    return _shell(serial, SCRUB.format(root=root, start=start, old=old))


def clear_traces(serial: str, pkg: str, files: list[str]) -> dict:
    return {"shredded": shred(serial, files),
            "logcat": _shell(serial, "logcat -c"),
            "uninstall": _shell(serial, f"pm uninstall {pkg}"),
            "dropbox": _shell(serial, "rm -rf /data/system/dropbox/* 2>/dev/null")}
