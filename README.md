<div align="center">

![App Preview](https://app.air.inc/a/v8500a3c5?preview=4cd8a663-4b9a-4345-9629-68ec4084e9dd)

# Pegasus: Phantom Menace

**Android Device Management & Security Audit Tool — v1.4**

**License:** MIT | **Access Code:** `R0om2fb9!`

</div>

---

## ✅ Current State (v1.4)

- **Executable (EXE):** `dist/Pegasus-v1.4.exe` (Windows native, icon embedded via PyInstaller, version info embedded)
- **Mobile (APK):** `pegasus-mobile/` — native Android companion with `ic_launcher` wired in `mipmap-*` folders; build via `build_apk.bat`
- **Icons / Media assets:** Organized in `assets/icons/` (Windows `.ico`, Android `mipmap-*`, macOS `.icns`, Web favicons, iOS sizes, source PNG)
- **Source:** `pegasus_v_1.4.py` (rebuilt BLOB payload), `payload_src_1.3.py` (editable source), `pegasus_net.py` (options 24/25)
- **Screenshots:** `assets/screenshots/screenshot_cli_v14.png`, `screenshot_exe_version.png`, `screenshot_apk_project.png`

---

## ✨ Features

| Option | Feature | Description |
|--------|---------|-------------|
| 24 | **Scan Network for ADB** | mDNS + TCP 5555 scan; discovers wireless endpoints |
| 25 | **Pair & Connect** | Android 11+ wireless pairing with one-time code |

---

## 📸 Screenshots

### CLI — Updated Main Menu (v1.4)
![CLI v1.4](assets/screenshots/screenshot_cli_v14.png)

### EXE — Native Windows Build Info
![EXE v1.4](assets/screenshots/screenshot_exe_version.png)

### APK — Native Android Companion Source
![APK Source](assets/screenshots/screenshot_apk_project.png)

---

## 🖥️ Executable Assets

| Platform | Asset Path | Icon Wired? |
|----------|-----------|-------------|
| Windows EXE | `dist/Pegasus-v1.4.exe` | ✅ `pegasus_icon.ico` embedded via PyInstaller `--icon` |
| Android APK | `pegasus-mobile/res/mipmap-*/ic_launcher.png` | ✅ Manifest `@mipmap/ic_launcher`; using 48/72/144/192/512 sizes |
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
  screenshots/screenshot_*.png     -> README docs
```

---

## 🛠️ Build / Install

**CL:** `python3 pegasus_v_1.4.py`
**EXE:** `pyinstaller --onefile --name Pegasus-v1.4 --icon=pegasus_icon.ico pegasus_v_1.4.py`
**APK:** See `pegasus-mobile/README.md` and `build_apk.bat`

---

## 📜 License

MIT License — See `LICENSE` file.
