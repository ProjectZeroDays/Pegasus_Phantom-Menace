import base64
import re
import zlib

src = open("pegasus_v_1.3.py", encoding="utf-8").read()
blob = re.search(r'BLOB = "(.+?)"', src, re.S).group(1)
raw = base64.b64decode(blob)
code = zlib.decompress(bytes([b ^ b"secret!"[i % 7] for i, b in enumerate(raw)])).decode()
checks = {
    "0-10 prompt": "Select cyber option (0-10)" in code,
    "single-pass helpers": "fetch_package_dump" in code and "parse_package_sections" in code,
    "record retry": "retrying once" in code,
    "no per-pkg loop": "dumpsys package {pkg}" not in code,
    "options 24/25": '"24": option_scan_network' in code and '"25": option_wireless_pair' in code,
}
for name, ok in checks.items():
    print(f"[{'OK' if ok else 'MISSING'}] {name}")
