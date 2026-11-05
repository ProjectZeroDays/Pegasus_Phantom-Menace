# DESN — Design Doc: Q9 / INFEROR / Pegasus Phantom Menace v2
# Date: 2026-11-03
# Purpose: Architecture linking Q9 header, 61 FULL features, weapons modules, UI, native delivery

## Components
- Q9 Header: lime-green [Q9] banner in qandroid_inferor_complete.py
- 61 Menu Features: battery/imei/record_mic/play_video/list_dir/delete_path/uninstall/tap/swipe/type_text/open_url/unlock_pin/lock_device/whatsapp_media/camera_folder + all others
- Weapons Integration: weapons/ (adb/badusb/bluetooth/botnet/ddos/crack/camwar) mapped to modules
- Catalog Index: exploit_catalog/ + payload_catalogue/ + exploit_payloads/ linked to integrated_exploits_payloads.py
- Native Build: build_native_q9.py (pyinstaller EXE + buildozer APK)
- UI: localhost:5000/tools (Pegasus Phantom Menace v2.1.0) — Toolbox / Access / Operations / Binary Console
- Log / Alert: /log/events.jsonl + /api/logs (main + categories + dashboard)
- Auth / Push: MSF localserver:7777 / msf / R0om2fb9!; Git push blocked by remote hook (HANDOFF present in PLAN.md)

## Change Log When/Where
- Q9 header: qandroid_inferor_complete.py (now embedded)
- Weapons wire: same + weapons/ directory
- Catalog dirs: root / exploit_catalog / payload_catalogue / exploit_payloads
- AppContext fixes: pegasus/core/plugin/__init__.py (get_payloads_dir/get_dna_dir/get_reports_dir)
- Backend guard: _noop + _SafeIO + http-handler kill (app.py / jobs.py)
- Log button: pegasus/core/__main__.py + /api/logs endpoint
- Build script: build_native_q9.py (ready; disk full blocked folder copy — use source)
\n--- DEFENSIVE DASHBOARD MAPPING ADDED 2026-11-03 ---\nA: dashboard-botnet-detection.md\nB: dashboard-ddos-deauth-detection.md\nC: dashboard-phishing-detection.md\nD: dashboard-brute-force-vault.md\nE: dashboard-fuzz-monitoring.md\nF: dashboard-ransomware-sandbox.md\nOffensive excluded; defensive only; settings/configurable all.\n