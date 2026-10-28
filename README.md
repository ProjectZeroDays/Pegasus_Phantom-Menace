<div align="center">

![App Preview](https://app.air.inc/a/v8500a3c5?preview=4cd8a663-4b9a-4345-9629-68ec4084e9dd)

# Pegasus: Phantom Menace

**Android Device Management & Security Audit Tool — v1.4**

**License:** MIT

</div>

---

## ✅ Current State (v1.4)

- **Executable (EXE):** `dist/Pegasus-v1.4.exe` (Windows native, icon embedded via PyInstaller, version info embedded)
- **Mobile (APK):** `pegasus-mobile/` — native Kotlin Android companion with embedded WebView loading the Pegasus dashboard, native bottom nav menu (Dashboard, Devices, Scan, Tools, More); build via `./gradlew assembleDebug`
- **Icons / Media assets:** Organized in `assets/icons/` (Windows `.ico`, Android `mipmap-*`, macOS `.icns`, Web favicons, iOS sizes, source PNG)
- **Source:** `pegasus_v_1.4.py` (rebuilt BLOB payload), `payload_src_1.3.py` (editable source), `pegasus_net.py` (options 24/25)
- **Screenshots:** `assets/screenshots/screenshot_android_mobile.svg`, `screenshot_ios_pwa.svg`, `screenshot_web_desktop.svg`, `screenshot_pwa_mobile.svg`

---

## ✨ Features

| Option | Feature | Description |
|--------|---------|-------------|
| 24 | **Scan Network for ADB** | mDNS + TCP 5555 scan; discovers wireless endpoints |
| 25 | **Pair & Connect** | Android 11+ wireless pairing with one-time code |
| 26 | **Extra Features (High-Value)** | 17 sub-features: AI Assistant, Report Generator, CVE Scanner, Live Dashboard, Telegram, Campaign Manager, Steganography, Mass Payload, DNA Tracker, AI Mutator, QR Delivery, SSL Bypass, Listener Monitor, ngrok, Network Forwarding, Network Scanner, and more |

---

## 📸 Screenshots

### Android — Native Kotlin Mobile App (WebView + Bottom Nav)
![Android Mobile](assets/screenshots/screenshot_android_mobile.svg)

### iOS — PWA in Safari (iOS-style Bottom Tab Bar)
![iOS PWA](assets/screenshots/screenshot_ios_pwa.svg)

### Web — Desktop Browser Dashboard
![Web Desktop](assets/screenshots/screenshot_web_desktop.svg)

### PWA — Standalone Mobile Web View
![PWA Mobile](assets/screenshots/screenshot_pwa_mobile.svg)

---

## 🖥️ Executable Assets

| Platform | Asset Path | Icon Wired? |
|----------|-----------|-------------|
| Windows EXE | `dist/Pegasus-v1.4.exe` | ✅ `pegasus_icon.ico` embedded via PyInstaller `--icon` |
| Android APK | `pegasus-mobile/app/src/main/res/mipmap-*/ic_launcher.png` | ✅ Manifest `@mipmap/ic_launcher`; using 48/72/144/192/512 sizes |
| macOS (future) | `assets/icons/macos/pegasus.icns` | ✅ Source icon ready |
| Web / Favicon | `assets/icons/web/favicon-*.png` + `pegasus_icon.png` | ✅ Source logo ready |

---

## 📁 Organize / Use Icons

```
assets/icons/
  windows/pegasus_icon.ico         -> EXE icon (PyInstaller)
  web/pegasus_icon.png             -> README/logo source
  macos/pegasus.icns               -> macOS app bundle
  android/android_*.png            -> Source for mipmap build
  screenshots/screenshot_*.svg     -> README docs (Android, iOS, Web, PWA)
```

---

### 🚀 Extra Features (Option 26) — High-Value Capabilities

Integrated from DeadDroid v2.0 — 17 sub-features:

| Sub-Option | Feature | Description |
|-----------|---------|-------------|
| 1 | **AI Assistant (Claude)** | Real-time pentest guidance via Claude AI |
| 2 | **Report Generator (HTML)** | Professional pentest reports with findings |
| 3 | **Android CVE Scanner** | Vulnerability fingerprinting via ADB + NVD API |
| 4 | **Live Dashboard** | Real-time device monitoring TUI |
| 5 | **Telegram Remote Control** | Push alerts + remote command execution |
| 6 | **Campaign Manager** | Organize penetration test assessments |
| 7 | **Steganography Delivery** | Hide payload URLs in images (LSB) |
| 8 | **Mass Payload Generator** | Batch payload generation with DNA tags |
| 9 | **Payload DNA Tracker** | Unique payload tracking system |
| 10 | **AI Mutation Engine** | AV evasion suggestions via Claude |
| 11 | **QR Payload Delivery** | Generate QR codes for payload URLs |
| 12 | **SSL Pinning Bypass** | Frida script generator |
| 13 | **Listener Health Monitor** | Port polling with alerts |
| 14 | **ngrok Tunnel Manager** | TCP/HTTP tunnel management |
| 15 | **Network & Port Forwarding** | socat/SSH/iptables forwarding |
| 16 | **Network Scanner (nmap)** | Host discovery and port scanning |

---

## 🛠️ Build / Install

**CL:** `python3 pegasus_v_1.4.py`
**EXE:** `pyinstaller --onefile --name Pegasus-v1.4 --icon=pegasus_icon.ico pegasus_v_1.4.py`
**APK:** See `pegasus-mobile/README.md` and `build_apk.bat`

---

## 📜 License

MIT License — See `LICENSE` file.
