"""Tool + device discovery.

All external binaries are invoked defensively: missing tools never raise, they
return a structured "unavailable" status the GUI renders as a red badge.
"""
from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from pegasus.core.config import get_settings

TOOL_SPECS: List[Dict[str, str]] = [
    {"key": "adb", "label": "ADB", "binary": "adb", "purpose": "Android device bridge", "required": "yes"},
    {"key": "fastboot", "label": "Fastboot", "binary": "fastboot", "purpose": "Bootloader operations", "required": "yes"},
    {"key": "scrcpy", "label": "scrcpy", "binary": "scrcpy", "purpose": "Screen mirroring", "required": "optional"},
    {"key": "nmap", "label": "nmap", "binary": "nmap", "purpose": "Network scanning", "required": "optional"},
    {"key": "msfvenom", "label": "msfvenom", "binary": "msfvenom", "purpose": "Payload generation", "required": "optional"},
    {"key": "frida", "label": "Frida", "binary": "frida", "purpose": "Runtime instrumentation", "required": "optional"},
    {"key": "apktool", "label": "apktool", "binary": "apktool", "purpose": "APK decompilation", "required": "optional"},
    {"key": "jadx", "label": "jadx", "binary": "jadx", "purpose": "Java decompilation", "required": "optional"},
    {"key": "tshark", "label": "TShark", "binary": "tshark", "purpose": "Packet capture", "required": "optional"},
    {"key": "wireshark", "label": "Wireshark", "binary": "wireshark", "purpose": "Packet analysis", "required": "optional"},
    {"key": "ngrok", "label": "ngrok", "binary": "ngrok", "purpose": "Tunnel management", "required": "optional"},
    {"key": "openssl", "label": "OpenSSL", "binary": "openssl", "purpose": "Certificates / crypto", "required": "optional"},
    {"key": "node", "label": "Node.js", "binary": "node", "purpose": "Web GUI toolchain", "required": "optional"},
    {"key": "git", "label": "Git", "binary": "git", "purpose": "Version control", "required": "optional"},
]


def run(cmd: List[str], timeout: float = 12.0, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Run a command, returning a structured result (never raises)."""
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            errors="replace",
        )
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "durationMs": int((time.time() - started) * 1000),
            "command": " ".join(cmd),
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "code": -1,
            "stdout": "",
            "stderr": f"{cmd[0]}: not found on PATH",
            "durationMs": int((time.time() - started) * 1000),
            "command": " ".join(cmd),
            "missing": True,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "code": -2,
            "stdout": "",
            "stderr": f"timed out after {timeout}s",
            "durationMs": int((time.time() - started) * 1000),
            "command": " ".join(cmd),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "code": -3,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "durationMs": int((time.time() - started) * 1000),
            "command": " ".join(cmd),
        }


def tool_version(binary: str) -> Optional[str]:
    path = shutil.which(binary) or shutil.which(binary + ".exe")
    if not path:
        return None
    for args in ([binary, "--version"], [binary, "version"], [binary, "-v"]):
        res = run(args, timeout=6)
        if res["ok"]:
            first = (res["stdout"] or res["stderr"]).strip().splitlines()
            if first:
                return first[0][:120]
    return "installed"


@dataclass
class ToolStatus:
    key: str
    label: str
    purpose: str
    required: str
    available: bool
    path: Optional[str]
    version: Optional[str]


def scan_tools() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for spec in TOOL_SPECS:
        path = shutil.which(spec["binary"]) or shutil.which(spec["binary"] + ".exe")
        out.append(
            asdict(
                ToolStatus(
                    key=spec["key"],
                    label=spec["label"],
                    purpose=spec["purpose"],
                    required=spec["required"],
                    available=bool(path),
                    path=path,
                    version=tool_version(spec["binary"]) if path else None,
                )
            )
        )
    return out


# ---------------------------------------------------------------------------
# ADB
# ---------------------------------------------------------------------------

def adb_devices() -> List[Dict[str, Any]]:
    """Parse `adb devices -l` into structured device records."""
    res = run(["adb", "devices", "-l"], timeout=14)
    if not res["ok"]:
        return []
    devices: List[Dict[str, Any]] = []
    for line in res["stdout"].splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        record: Dict[str, Any] = {
            "serial": serial,
            "state": state,
            "model": None,
            "product": None,
            "device": None,
            "transport": "usb",
            "isNetwork": ":" in serial,
        }
        for part in parts[2:]:
            if ":" in part:
                k, v = part.split(":", 1)
                if k in ("model", "product", "device", "transport"):
                    record[k] = v
        devices.append(record)
    return devices


def adb_props(serial: str) -> Dict[str, Any]:
    """Full, portable device fingerprint (single `getprop` call)."""
    res = run(["adb", "-s", serial, "shell", "getprop"], timeout=20)
    props: Dict[str, str] = {}
    if res["ok"]:
        for line in res["stdout"].splitlines():
            line = line.strip()
            if line.startswith("[") and "]" in line:
                key = line[1 : line.index("]")]
                rest = line[line.index("]") + 1 :].strip()
                value = rest
                if rest.startswith("["):
                    end = rest.rfind("]")
                    value = rest[1:end] if end > 0 else rest[1:]
                props[key] = value.strip()
    return props


def device_detail(serial: str) -> Dict[str, Any]:
    """Everything the GUI shows on a device card."""
    props = adb_props(serial)
    battery = run(["adb", "-s", serial, "shell", "dumpsys", "battery"], timeout=14)
    level = None
    for line in battery["stdout"].splitlines():
        if "level:" in line:
            try:
                level = int(line.split("level:")[1].strip())
            except ValueError:
                pass
    su = run(["adb", "-s", serial, "shell", "which", "su"], timeout=10)
    storage = run(["adb", "-s", serial, "shell", "df", "/data"], timeout=14)
    total = free = None
    lines = [l for l in storage["stdout"].splitlines() if l.strip()]
    if len(lines) > 1:
        fields = lines[-1].split()
        if len(fields) >= 4:
            try:
                total_kb = int(fields[1])
                free_kb = int(fields[3])
                total = total_kb * 1024
                free = free_kb * 1024
            except ValueError:
                pass
    return {
        "serial": serial,
        "model": props.get("ro.product.model", "Unknown"),
        "manufacturer": props.get("ro.product.manufacturer", "Unknown"),
        "device": props.get("ro.product.device", ""),
        "androidVersion": props.get("ro.build.version.release", "Unknown"),
        "apiLevel": int(props.get("ro.build.version.sdk", "0") or 0),
        "securityPatch": props.get("ro.build.version.security_patch", "Unknown"),
        "buildId": props.get("ro.build.id", "Unknown"),
        "buildType": props.get("ro.build.type", "Unknown"),
        "buildTags": props.get("ro.build.tags", "Unknown"),
        "abi": props.get("ro.product.cpu.abi", "Unknown"),
        "fingerprint": props.get("ro.build.fingerprint", "Unknown"),
        "batteryLevel": level,
        "isRooted": bool(su["stdout"].strip()),
        "storageTotal": total,
        "storageFree": free,
        "properties": props,
    }


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# System / environment
# ---------------------------------------------------------------------------

def workspace_info() -> Dict[str, Any]:
    settings = get_settings()
    return {
        "workspace": str(settings.get_workspace_path()),
        "database": settings.database.type,
        "databasePath": str(settings.database.path),
        "reportsDir": str(settings.get_reports_dir()),
        "payloadsDir": str(settings.get_payloads_dir()),
        "logsDir": str(settings.get_logs_dir()),
        "aiConfigured": bool(settings.ai.api_key),
        "aiModel": settings.ai.model,
        "metasploit": f"{settings.metasploit.rpc_host}:{settings.metasploit.rpc_port}",
        "version": settings.app.version,
    }


def environment_info() -> Dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "hostname": hostname(),
        "localIp": local_ip(),
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    }


def port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def listener_status(host: str = "127.0.0.1", ports: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    ports = ports or [4444, 5555, 55553, 8080, 8443, 5000]
    return [{"host": host, "port": p, "open": port_open(host, p)} for p in ports]
