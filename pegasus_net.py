#!/usr/bin/env python3
# Pegasus - Wireless ADB Network Tools (Options 24 & 25)
#   Option 24: scan the local network for ADB endpoints (mDNS + TCP probe)
#   Option 25: Android 11+ wireless pairing & connect (no USB required)
# Use for Educational Purpose Only - only on networks/devices you own
# or have explicit written permission to test.
import ipaddress
import os
import re
import shutil
import socket
import struct
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

# ----------------- Colors (same palette as Pegasus payload) -----------------
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
CYAN = "\033[1;36m"
RESET = "\033[0m"

ADB_PORT = 5555          # classic wireless ADB (adb tcpip 5555)
SCAN_TIMEOUT = 0.35      # per-host TCP connect timeout (seconds)
MAX_WORKERS = 128        # concurrent scan threads
PROBE_TIMEOUT = 1.0      # ADB handshake read timeout
MAX_AUTO_SCAN_HOSTS = 1024  # ask for confirmation beyond this many hosts

# ----------------- Small helpers -----------------

def _run(cmd, timeout=15):
    """Run a shell command, capture output. Never raises."""
    try:
        res = subprocess.run(cmd, shell=True, check=False,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, errors="replace", timeout=timeout)
        return (res.stdout or "").strip(), (res.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return "", "timeout"
    except Exception as e:
        return "", str(e)


def _ask(prompt, default=""):
    """input() that survives EOF so piped/non-interactive runs never crash."""
    try:
        value = input(prompt).strip()
    except EOFError:
        print()
        return default
    return value if value else default


def _validate_endpoint(endpoint):
    return re.fullmatch(r"(\[[0-9a-fA-F:.]+\]|[A-Za-z0-9._-]+):\d{1,5}", endpoint) is not None


# ----------------- Local network discovery -----------------

def _get_local_ip():
    """Local IPv4 of the default route (UDP connect trick, no packets sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _mask_to_prefix(mask_str):
    return bin(int(ipaddress.IPv4Address(mask_str))).count("1")


def _get_network(local_ip):
    """Best-effort IPv4Network for local_ip; falls back to /24."""
    prefix = None
    try:
        if os.name == "nt":
            out, _ = _run("ipconfig")
            lines = out.splitlines()
            for i, line in enumerate(lines):
                if local_ip in line:
                    # Windows: "IPv4 Address... : x.x.x.x" followed by "Subnet Mask... : m.m.m.m"
                    for nxt in lines[i + 1:i + 5]:
                        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", nxt)
                        if m and not m.group(1).startswith("0."):
                            mask = m.group(1)
                            if int(mask.split(".")[0]) >= 128:
                                prefix = _mask_to_prefix(mask)
                                break
                    break
        else:
            for cmd, pattern in (
                (r"ip -4 addr show", None),          # Linux / Termux: inet a.b.c.d/nn
                (r"ifconfig", "ifconfig"),           # macOS / Android: netmask m.m.m.m | 0xnnnnnnnn
            ):
                out, _ = _run(cmd)
                if not out:
                    continue
                if pattern is None:
                    m = re.search(re.escape(local_ip) + r"/(\d{1,2})", out)
                    if m:
                        prefix = int(m.group(1))
                        break
                else:
                    for line in out.splitlines():
                        if local_ip in line:
                            m = re.search(r"netmask\s+(0x[0-9a-fA-F]+|\d{1,3}(?:\.\d{1,3}){3})", line)
                            if m:
                                val = m.group(1)
                                prefix = (bin(int(val, 16)).count("1") if val.startswith("0x")
                                          else _mask_to_prefix(val))
                                break
                    if prefix is not None:
                        break
    except Exception:
        prefix = None
    if prefix is None:
        prefix = 24
    return ipaddress.ip_network(f"{local_ip}/{prefix}", strict=False)


def mdns_services():
    """Parse `adb mdns services` -> (connect_endpoints, pairing_endpoints)."""
    if not shutil.which("adb"):
        return [], []
    out, _ = _run("adb mdns services", timeout=10)
    connect_eps, pairing_eps = [], []
    for line in out.splitlines():
        m = re.search(r"ADB Tls (connect|pairing)\s+(\S+)", line, re.I)
        if m:
            endpoint = m.group(2)
            bucket = connect_eps if m.group(1).lower() == "connect" else pairing_eps
            if endpoint not in bucket:
                bucket.append(endpoint)
    return connect_eps, pairing_eps


def list_devices_with_state():
    """[(serial, state), ...] from `adb devices`, skipping daemon noise."""
    out, _ = _run("adb devices")
    devices = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("List of"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def show_devices():
    devs = list_devices_with_state()
    if not devs:
        print(YELLOW + "[*] No devices connected." + RESET)
        return
    print(CYAN + "[*] Device list:" + RESET)
    for serial, state in devs:
        color = GREEN if state == "device" else (YELLOW if state == "unauthorized" else RED)
        print(f"    {color}{serial:<40} {state}{RESET}")


# ----------------- ADB endpoint probing -----------------

def _probe_adb(ip, port):
    """Send a raw ADB CNXN handshake and read the reply.

    Returns:  "auth"  -> confirmed ADB, wants authorization (never trusted this PC)
              "adb"   -> confirmed ADB (already authorized / speaks protocol)
              "open"  -> port open, reply not ADB (or silent)
              None    -> nothing listening / unreachable
    """
    try:
        with socket.create_connection((ip, port), timeout=PROBE_TIMEOUT) as s:
            s.settimeout(PROBE_TIMEOUT)
            payload = b"host::\x00"
            # ADB packet header: cmd, arg0, arg1, len, sum(payload), magic
            header = struct.pack(
                "<6I",
                0x4E584E43,                    # A_CNXN 'CNXN'
                0x01000001,                    # protocol version
                0x00100000,                    # max data payload
                len(payload),
                sum(payload) & 0xFFFFFFFF,     # classic ADB checksum (sum of bytes)
                0x4E584E43 ^ 0xFFFFFFFF,       # magic = cmd ^ 0xffffffff
            )
            s.sendall(header + payload)
            buf = b""
            deadline = time.time() + PROBE_TIMEOUT
            while len(buf) < 24 and time.time() < deadline:
                try:
                    chunk = s.recv(24 - len(buf))
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf += chunk
            if len(buf) >= 4:
                cmd = buf[:4]
                if cmd == b"AUTH":
                    return "auth"
                if cmd in (b"CNXN", b"CLSE", b"OKAY"):
                    return "adb"
                return "open"
            return "open"
    except (ConnectionRefusedError, socket.timeout, OSError):
        return None


# ----------------- ADB actions -----------------

def _adb_connect(target):
    out, err = _run(f"adb connect {target}", timeout=10)
    msg = (out or err).strip()
    low = msg.lower()
    if "failed" in low or "cannot" in low or "unable" in low:
        print(RED + f"[!] {msg}" + RESET)
        return False
    if "already connected" in low:
        print(GREEN + f"[+] {msg}" + RESET)
        return True
    if "connected to" in low:
        print(GREEN + f"[+] {msg}" + RESET)
        return True
    print(YELLOW + f"[?] {msg or 'no response'}" + RESET)
    return False


def _adb_pair(endpoint, code):
    out, err = _run(f"adb pair {endpoint} {code}", timeout=20)
    return (out or "") + "\n" + (err or "")


# ----------------- Option 24: network scan -----------------

def _tcp_scan(network, timeout=SCAN_TIMEOUT):
    """Concurrent connect-scan of every host in network on ADB_PORT."""
    hosts = [str(h) for h in network.hosts()]
    if len(hosts) > 2:
        hosts = [h for h in hosts if h != _get_local_ip()] or hosts

    def check(ip):
        try:
            with socket.create_connection((ip, ADB_PORT), timeout=timeout):
                return ip
        except OSError:
            return None

    open_hosts = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for result in ex.map(check, hosts):
            if result:
                open_hosts.append(result)
    return open_hosts


def scan_network_menu():
    print(CYAN + "\n[+] Wireless ADB Network Scan" + RESET)
    if not shutil.which("adb"):
        print(RED + "[!] adb not found in PATH - install platform-tools first." + RESET)
        return
    print(YELLOW + "[*] Only scan networks you own or have permission to test." + RESET)

    local_ip = _get_local_ip()
    if local_ip.startswith("127."):
        print(RED + "[!] Could not determine local network (no route / offline?)." + RESET)
        return
    network = _get_network(local_ip)
    host_count = max(network.num_addresses - 2, 0)
    print(GREEN + f"[*] Local IP : {local_ip}" + RESET)
    print(GREEN + f"[*] Network  : {network}  ({host_count} hosts)" + RESET)

    if host_count > MAX_AUTO_SCAN_HOSTS:
        est = int(host_count * SCAN_TIMEOUT / MAX_WORKERS) + 1
        ans = _ask(YELLOW + f"[?] Large network - scan may take ~{est}s. Proceed? [y/N]: " + RESET, "n")
        if ans.lower() != "y":
            print(YELLOW + "[*] Scan cancelled." + RESET)
            return

    # ---- Step 1: mDNS discovery (Android 11+ wireless debugging) ----
    print(CYAN + "\n[*] Step 1/2: mDNS service discovery (adb mdns services)..." + RESET)
    connect_eps, pairing_eps = mdns_services()
    if connect_eps:
        for ep in connect_eps:
            print(GREEN + f"    [+] ADB TLS connect  : {ep}" + RESET)
    if pairing_eps:
        for ep in pairing_eps:
            print(YELLOW + f"    [+] ADB TLS pairing  : {ep}" + RESET)
    if not connect_eps and not pairing_eps:
        print(YELLOW + "    [-] No mDNS ADB services found (enable Wireless debugging on the device)." + RESET)

    # ---- Step 2: TCP scan of classic wireless ADB port ----
    print(CYAN + f"\n[*] Step 2/2: TCP scan port {ADB_PORT} (wireless ADB)..." + RESET)
    started = time.time()
    open_hosts = _tcp_scan(network)
    print(GREEN + f"[*] Scan finished in {time.time() - started:.1f}s" + RESET)

    candidates = []
    for ip in open_hosts:
        state = _probe_adb(ip, ADB_PORT)
        if state == "adb":
            print(GREEN + f"    [+] {ip}:{ADB_PORT} - ADB confirmed (authorized)" + RESET)
            candidates.append(f"{ip}:{ADB_PORT}")
        elif state == "auth":
            print(GREEN + f"    [+] {ip}:{ADB_PORT} - ADB confirmed (will ask to authorize on device)" + RESET)
            candidates.append(f"{ip}:{ADB_PORT}")
        elif state == "open":
            print(YELLOW + f"    [-] {ip}:{ADB_PORT} - open, but not identified as ADB" + RESET)
        else:
            print(YELLOW + f"    [-] {ip}:{ADB_PORT} - open (probe inconclusive)" + RESET)

    if not open_hosts:
        print(YELLOW + "\n[-] No wireless ADB hosts found." + RESET)
        print(YELLOW + "    Hints: run `adb tcpip 5555` once over USB, or use Android 11+" + RESET)
        print(YELLOW + "    Wireless debugging (Option 25 pairs without USB), and make sure" + RESET)
        print(YELLOW + "    devices are on the same Wi-Fi (AP/client isolation blocks scans)." + RESET)

    # ---- Already-connected devices ----
    show_devices()

    # ---- Offer to connect ----
    if candidates:
        ans = _ask(CYAN + f"\n[?] Connect to detected device(s)? [y/N]: " + RESET, "n")
        if ans.lower() == "y":
            for target in candidates:
                _adb_connect(target)
            show_devices()
            print(YELLOW + "[*] If a device shows 'unauthorized', tap Allow on its USB-debugging prompt." + RESET)


# ----------------- Option 25: pair & connect -----------------

def _select_endpoint(endpoints, kind):
    """Pick one endpoint from a list (auto if exactly one). Returns '' on cancel."""
    if not endpoints:
        return ""
    if len(endpoints) == 1:
        ans = _ask(YELLOW + f"[?] Use {kind} endpoint {endpoints[0]}? [Y/n]: " + RESET, "y")
        return endpoints[0] if ans.lower() in ("y", "") else ""
    print(CYAN + f"[*] Available {kind} endpoints:" + RESET)
    for i, ep in enumerate(endpoints, 1):
        print(f"    [{i}] {ep}")
    ans = _ask(GREEN + f"Select 1-{len(endpoints)} (0 to cancel): " + RESET, "0")
    if ans.isdigit() and 1 <= int(ans) <= len(endpoints):
        return endpoints[int(ans) - 1]
    return ""


def _connect_after_pair(connect_eps):
    """After a successful pairing, establish the actual ADB connection."""
    time.sleep(0.5)
    fresh_connect, _ = mdns_services()
    candidates = fresh_connect or connect_eps
    endpoint = _select_endpoint(candidates, "connect")
    if not endpoint:
        endpoint = _ask(YELLOW + "Enter connect IP:PORT (from the Wireless debugging screen): " + RESET)
    if endpoint:
        if _validate_endpoint(endpoint):
            _adb_connect(endpoint)
        else:
            print(RED + "[!] Invalid endpoint. Use IP:PORT (e.g. 192.168.1.20:5555)." + RESET)
    show_devices()


def _pair_flow(pairing_eps, connect_eps):
    print(CYAN + "\n[+] Pair with a new device (Android 11+ Wireless debugging)" + RESET)
    print(YELLOW + "    Device: Settings -> Developer options -> Wireless debugging" + RESET)
    print(YELLOW + "            -> 'Pair device with pairing code' (code expires quickly)" + RESET)

    endpoint = _select_endpoint(pairing_eps, "pairing")
    if not endpoint:
        endpoint = _ask(YELLOW + "Enter pairing IP:PORT shown on the device: " + RESET)
    if not endpoint:
        print(YELLOW + "[*] Pairing cancelled." + RESET)
        return
    if not _validate_endpoint(endpoint):
        print(RED + "[!] Invalid endpoint. Use IP:PORT (e.g. 192.168.1.20:37089)." + RESET)
        return

    code = _ask(YELLOW + "Enter the 6-digit Wi-Fi pairing code: " + RESET)
    if not re.fullmatch(r"\d{6}", code):
        print(RED + "[!] Pairing code must be 6 digits." + RESET)
        return

    print(CYAN + f"[*] Pairing with {endpoint}..." + RESET)
    result = _adb_pair(endpoint, code)
    if "successfully paired" in result.lower():
        print(GREEN + f"[+] {result.splitlines()[0]}" + RESET)
        print(CYAN + "[*] Establishing ADB connection..." + RESET)
        _connect_after_pair(connect_eps)
    else:
        print(RED + "[!] Pairing failed:" + RESET)
        print(RED + "    " + (result.strip() or "no response from adb") + RESET)
        print(YELLOW + "    Checklist: device must be on the pairing-code screen, same Wi-Fi," + RESET)
        print(YELLOW + "    Wireless debugging ON, code expires after ~2 minutes." + RESET)


def pair_connect_menu():
    print(CYAN + "\n[+] Pair & Connect - Wireless ADB (no USB needed)" + RESET)
    print(YELLOW + "    Works with Android 11+ 'Wireless debugging'. Devices you have never" + RESET)
    print(YELLOW + "    connected before are paired with a one-time code shown on the device." + RESET)
    while True:
        connect_eps, pairing_eps = mdns_services()
        print(CYAN + "\n[*] mDNS discovery:" + RESET)
        print(f"    Pairing endpoints : {', '.join(pairing_eps) or 'none found'}")
        print(f"    Connect endpoints : {', '.join(connect_eps) or 'none found'}")
        print(YELLOW + "\n    [1] Pair with a new device (6-digit code, no USB)" + RESET)
        print(YELLOW + "    [2] Connect to a discovered endpoint" + RESET)
        print(YELLOW + "    [3] Manual connect (IP:PORT)" + RESET)
        print(YELLOW + "    [0] Back to main menu" + RESET)
        choice = _ask(GREEN + "Select (0-3): " + RESET, "0")
        if choice == "0":
            return
        elif choice == "1":
            _pair_flow(pairing_eps, connect_eps)
        elif choice == "2":
            endpoint = _select_endpoint(connect_eps, "connect")
            if endpoint:
                _adb_connect(endpoint)
                show_devices()
            elif not connect_eps:
                print(YELLOW + "[*] No discovered endpoints - use option 3 or pair first (option 1)." + RESET)
        elif choice == "3":
            target = _ask(YELLOW + "Enter IP:PORT to connect: " + RESET)
            if target:
                if _validate_endpoint(target):
                    _adb_connect(target)
                    show_devices()
                else:
                    print(RED + "[!] Invalid endpoint. Use IP:PORT (e.g. 192.168.1.20:5555)." + RESET)
        else:
            print(RED + "Invalid option." + RESET)
