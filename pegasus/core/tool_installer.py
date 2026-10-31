#!/usr/bin/env python3
"""Tool installer — installs missing Pegasus dependencies on Windows/macOS/Linux.

Strategy per tool (in order of preference):
  1. Already on PATH — skip.
  2. Python package (frida) — pip install.
  3. winget / apt / brew package.
  4. Direct download from the vendor into ~/.pegasus/tools/<name>.

Tools land in ~/.pegasus/tools and the directory is prepended to PATH for the
running process, so detection picks them up without a reinstall.
"""
from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Callable

TOOLS_DIR = Path.home() / ".pegasus" / "tools"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_path() -> None:
    """Prepend the tools dir to PATH for this process (and children)."""
    s = str(TOOLS_DIR)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if s not in parts:
        os.environ["PATH"] = s + os.pathsep + os.pathsep.join(parts)
    # Wireshark's tshark installs to Program Files — expose it if present
    ws = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Wireshark"
    if ws.exists() and str(ws) not in parts:
        os.environ["PATH"] = str(ws) + os.pathsep + os.environ["PATH"]


def _win() -> bool:
    return platform.system() == "Windows"


def _run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _winget_available() -> bool:
    if not _win():
        return False
    rc, _ = _run(["winget", "--version"], timeout=20)
    return rc == 0


def _download(url: str, dest: Path) -> Path:
    import requests
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return dest


def _mark_executable(path: Path) -> None:
    if not _win():
        path.chmod(path.stat().st_size and (path.stat().st_mode | stat.S_IEXEC))


# ---------------------------------------------------------------------------
# Individual installers — each returns (status, detail)
# ---------------------------------------------------------------------------

def _install_frida() -> tuple[str, str]:
    if shutil.which("frida") or shutil.which("frida.exe"):
        return ("present", "frida already on PATH")
    rc, out = _run([sys.executable, "-m", "pip", "install", "frida-tools"])
    return ("installed" if rc == 0 else "error", out[-300:])


APKTOOL_JAR_URLS = [
    "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar",
    "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.2.jar",
    "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar",
]


def _install_apktool() -> tuple[str, str]:
    jar = TOOLS_DIR / "apktool.jar"
    if not jar.exists():
        last_err = None
        for url in APKTOOL_JAR_URLS:
            try:
                _download(url, jar)
                break
            except Exception as exc:  # noqa: BLE001 — try next mirror
                last_err = exc
        else:
            return ("error", f"all mirrors failed: {last_err}")
    if _win():
        wrapper = TOOLS_DIR / "apktool.bat"
        if not wrapper.exists():
            _download("https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/windows/apktool.bat", wrapper)
        return ("installed", f"{wrapper} (jar {jar.name})")
    exe = TOOLS_DIR / "apktool"
    if not exe.exists():
        _download("https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool", exe)
        _mark_executable(exe)
    return ("installed", str(exe))


def _install_jadx() -> tuple[str, str]:
    suffix = "zip" if _win() else "tar.gz"
    ver = "1.5.0"
    name = f"jadx-{ver}"
    dest_dir = TOOLS_DIR / name
    bin_name = "jadx.bat" if _win() else "jadx"
    if (dest_dir / "bin" / bin_name).exists():
        # link into tools dir root
        link = TOOLS_DIR / bin_name
        if not link.exists():
            if _win():
                link.write_text(f'@echo off\r\n"{dest_dir}\\bin\\jadx.bat" %*\r\n')
            else:
                try:
                    link.symlink_to(dest_dir / "bin" / "jadx")
                except OSError:
                    shutil.copy2(dest_dir / "bin" / "jadx", link)
                    _mark_executable(link)
        return ("present", str(dest_dir))
    url = f"https://github.com/skylot/jadx/releases/download/v{ver}/jadx-{ver}.zip" if _win() else \
          f"https://github.com/skylot/jadx/releases/download/v{ver}/jadx-{ver}.zip"
    z = _download(url, TOOLS_DIR / f"jadx-{ver}.zip")
    with zipfile.ZipFile(z) as zf:
        zf.extractall(TOOLS_DIR)
    z.unlink()
    link = TOOLS_DIR / bin_name
    if not link.exists():
        if _win():
            link.write_text(f'@echo off\r\n"{dest_dir}\\bin\\jadx.bat" %*\r\n')
        else:
            try:
                link.symlink_to(dest_dir / "bin" / "jadx")
            except OSError:
                shutil.copy2(dest_dir / "bin" / "jadx", link)
                _mark_executable(link)
    return ("installed", str(dest_dir))


def _install_tshark_wireshark() -> tuple[str, str]:
    """tshark ships with Wireshark; install the whole app and expose tshark.exe."""
    if shutil.which("tshark") or shutil.which("tshark.exe"):
        return ("present", "tshark already on PATH")
    if _winget_available():
        rc, out = _run(["winget", "install", "--id=WiresharkFoundation.Wireshark", "-e", "--accept-source-agreements", "--accept-package-agreements"])
        if rc == 0:
            _persist_path()
            ensure_path()
            return ("installed", "winget: Wireshark (tshark included)")
        return ("error", out[-300:])
    return ("error", "winget unavailable — install Wireshark manually")


def _persist_path() -> None:
    """Persist the tools dir into the user PATH (Windows registry, HKCU)."""
    if not _win():
        return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""
        parts = [p for p in (current or "").split(os.pathsep) if p]
        changed = False
        for add in (str(TOOLS_DIR),):
            if add not in parts:
                parts.append(add)
                changed = True
        ws = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Wireshark"
        if ws.exists() and str(ws) not in parts:
            parts.append(str(ws))
            changed = True
        if changed:
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, os.pathsep.join(parts))
        key.Close()
    except Exception:
        pass


def _install_ngrok() -> tuple[str, str]:
    if shutil.which("ngrok") or shutil.which("ngrok.exe"):
        return ("present", "ngrok already on PATH")
    if _win():
        exe = TOOLS_DIR / "ngrok.exe"
        if not exe.exists():
            _download("https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip",
                      TOOLS_DIR / "ngrok.zip")
            with zipfile.ZipFile(TOOLS_DIR / "ngrok.zip") as zf:
                zf.extractall(TOOLS_DIR)
            (TOOLS_DIR / "ngrok.zip").unlink()
        return ("installed", str(exe))
    exe = TOOLS_DIR / "ngrok"
    if not exe.exists():
        _download("https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz",
                  TOOLS_DIR / "ngrok.tgz")
        with tarfile.open(TOOLS_DIR / "ngrok.tgz") as tf:
            tf.extractall(TOOLS_DIR)
        (TOOLS_DIR / "ngrok.tgz").unlink()
        _mark_executable(exe)
    return ("installed", str(exe))


INSTALLERS: dict[str, Callable[[], tuple[str, str]]] = {
    "frida": _install_frida,
    "apktool": _install_apktool,
    "jadx": _install_jadx,
    "tshark": _install_tshark_wireshark,
    "wireshark": _install_tshark_wireshark,
    "ngrok": _install_ngrok,
}


def install(key: str) -> dict:
    """Install one tool by key. Returns a status dict."""
    ensure_path()
    fn = INSTALLERS.get(key)
    if not fn:
        return {"key": key, "status": "error", "detail": f"no installer for {key}"}
    try:
        status, detail = fn()
        if status in ("installed", "present"):
            _persist_path()
            ensure_path()
        return {"key": key, "status": status, "detail": str(detail)[-400:]}
    except Exception as exc:  # noqa: BLE001
        return {"key": key, "status": "error", "detail": f"{type(exc).__name__}: {exc}"}


def install_missing(keys: list[str] | None = None) -> list[dict]:
    """Install every missing tool (or the given keys). Returns per-tool status."""
    from pegasus.ui.web.backend.tools import TOOL_SPECS
    ensure_path()
    results = []
    wanted = keys or [s["key"] for s in TOOL_SPECS]
    for spec in TOOL_SPECS:
        if spec["key"] not in wanted:
            continue
        binary = spec["binary"]
        if shutil.which(binary) or shutil.which(binary + ".exe"):
            results.append({"key": spec["key"], "status": "present", "detail": "already on PATH"})
            continue
        if spec["key"] in INSTALLERS:
            results.append(install(spec["key"]))
        else:
            results.append({"key": spec["key"], "status": "missing", "detail": "no auto-installer — install manually"})
    return results
