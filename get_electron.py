#!/usr/bin/env python3
"""get_electron.py - install the electron binary without npm or Invoke-WebRequest."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "electron" / "node_modules" / "electron"
TMP = ROOT / ".pytest-tmp"
TMP.mkdir(exist_ok=True)
E = {**os.environ, "PYTHONIOENCODING": "utf-8"}

if not (BASE / "package.json").exists():
    print("node_modules/electron missing - run: npm.cmd ci --ignore-scripts  (in electron/)")
    raise SystemExit(1)

VER = __import__("json").loads((BASE / "package.json").read_text(encoding="utf-8"))["version"]
FILE = f"electron-v{VER}-win32-x64.zip"
SOURCES = [
    ("github", f"https://github.com/electron/electron/releases/download/v{VER}/{FILE}",
     f"https://github.com/electron/electron/releases/download/v{VER}/SHASUMS256.txt"),
    ("npmmirror", f"https://npmmirror.com/mirrors/electron/{VER}/{FILE}",
     f"https://npmmirror.com/mirrors/electron/{VER}/SHASUMS256.txt"),
]
print(f"electron {VER}")

CURL = shutil.which("curl") or r"C:\Windows\System32\curl.exe"


def fetch(url: str, out: Path, label: str) -> bool:
    print(f"\n-- {label}: {url}")
    if out.exists():
        out.unlink()

    if os.path.exists(CURL):
        print("   curl")
        p = subprocess.run([CURL, "-L", "--fail", "--retry", "3", "--retry-delay", "2",
                            "--connect-timeout", "30", "--max-time", "1800",
                            "-o", str(out), url],
                           capture_output=True, text=True, errors="replace", env=E)
        print("   exit " + str(p.returncode))
        for line in ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-6:]:
            print("   " + line[:150])
    else:
        print("   curl not found - python urllib")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pegasus-install"})
            with urllib.request.urlopen(req, timeout=120) as r, out.open("wb") as fh:
                shutil.copyfileobj(r, fh)
        except Exception as exc:
            print("   " + repr(exc)[:200])

    if out.exists():
        print("   " + str(out.stat().st_size) + " B")
    return out.exists() and out.stat().st_size > 1_000_000


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


zip_path = TMP / FILE
sum_path = TMP / "SHASUMS256.txt"
ok = False

for label, url, sums in SOURCES:
    if not fetch(url, zip_path, label):
        print("   too small / missing")
        continue
    want = None
    if fetch(sums, sum_path, label + " sums"):
        for line in sum_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().endswith(FILE):
                want = line.split()[0]
    got = sha(zip_path)
    print("   sha256 " + got)
    if want:
        print("   expect " + want)
        if got.lower() != want.lower():
            print("   MISMATCH")
            continue
        print("   hash verified")
    else:
        print("   no sums available - continuing on size alone")
    ok = True
    break

if not ok:
    print("\nAll sources failed. Check the network, a proxy, or AV interception,")
    print("then re-run. Nothing has been changed.")
    raise SystemExit(1)

dist = BASE / "dist"
if dist.exists():
    shutil.rmtree(dist, ignore_errors=True)
dist.mkdir(parents=True)
print("\nextracting")
with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(dist)
(BASE / "path.txt").write_text("electron.exe", encoding="utf-8")

exe = dist / "electron.exe"
print("electron.exe " + ("present " + str(exe.stat().st_size) + " B" if exe.exists() else "MISSING"))
if not exe.exists():
    raise SystemExit(1)

p = subprocess.run(["node", "-e", "console.log(require('electron'))"],
                   cwd=ROOT / "electron", capture_output=True, text=True, errors="replace", env=E)
print("require -> " + ("ok " + p.stdout.strip()[:80] if p.returncode == 0 else "THROWS\n" + p.stderr[-500:]))
raise SystemExit(0 if p.returncode == 0 else 1)