#!/usr/bin/env python3
"""Tool state/version search — runs at server startup to audit available tools."""
import subprocess, os, sys

def check(cmd, label):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        version = result.stdout.strip().splitlines()[0] if result.stdout else "installed"
        return f"{label}\tready\t{version}"
    except Exception as e:
        return f"{label}\tmissing\t—"

tools = [
    ("adb version", "ADB"),
    ("fastboot --version", "Fastboot"),
    ("scrcpy --version", "scrcpy"),
    ("nmap --version", "nmap"),
    ("msfvenom --version", "msfvenom"),
    ("frida --version", "Frida"),
    ("apktool --version", "apktool"),
    ("jadx --version", "jadx"),
    ("tshark --version", "TShark"),
    ("wireshark --version", "Wireshark"),
    ("ngrok version", "ngrok"),
    ("openssl version", "OpenSSL"),
    ("node --version", "Node.js"),
    ("git --version", "Git"),
]

print("Tool\tState\tVersion")
for cmd, label in tools:
    print(check(cmd, label))

# Write audit file
with open("C:/Projects/Pegasus_Phantom-Menace/log/tool_audit.txt", "w") as f:
    f.write("Tool\tState\tVersion\n")
    for cmd, label in tools:
        f.write(check(cmd, label) + "\n")
print("Audit written to log/tool_audit.txt")
