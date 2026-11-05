#!/bin/bash
# Server-start audit: runs every time python -m pegasus.ui.web.backend.app starts
# Searches for ADB, Fastboot, scrcpy, nmap, msfvenom, Frida, apktool, jadx, TShark, Wireshark, ngrok, OpenSSL, Node.js, Git
python pegasus/workflows/search_tool_state.py
echo "Status audit complete — tool readiness logged to log/tool_audit.txt"
