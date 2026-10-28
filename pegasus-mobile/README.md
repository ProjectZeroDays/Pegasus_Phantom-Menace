# Pegasus Mobile — Native Kotlin Android App

A native Kotlin Android companion app for Pegasus: Phantom Menace. Loads the
Pegasus web dashboard inside an embedded WebView with full Android integration
and a native bottom navigation menu.

## Features

- **Native Kotlin** Android app (100% Kotlin, no Java legacy)
- **Embedded WebView** — loads the Pegasus web dashboard natively
- **Bottom navigation menu** — native BottomNavigationView with Dashboard, Devices, Scan, Tools, and More sections
- **Deep link support** — `pegasus://pegasus/launch` opens the Pegasus dashboard
- **Browser fallback** — if the dashboard fails to load, offers retry/open-in-browser
- **Material Design** — dark theme, native status bar, bottom nav bar
- **SDK 21+** (Android 5.0) to **SDK 34** (Android 14)

## Bottom Navigation Controls

The native bottom nav menu provides quick access to Pegasus dashboard sections:

| Tab | Section | WebView Path | Purpose |
|-----|---------|--------------|---------|
| Dashboard | Home | `/` | Device status overview, connected devices, quick actions |
| Devices | Device Manager | `/devices` | Connected Android devices, ADB status, device fingerprinting |
| Scan | Network Scan | `/scan` | mDNS + TCP 5555 scan, wireless ADB discovery, pairing |
| Tools | Security Tools | `/tools` | Payload generator, FRP bypass, exploits, steganography |
| More | Settings | `/more` | License info, about, settings, help, logout |

The bottom nav is **native Android UI** (not web), so it remains accessible
even when the WebView content changes. Selecting a tab loads the corresponding
section in the WebView above.

## Project Structure

```
pegasus-mobile/
├── build.gradle                  # Project-level build config
├── settings.gradle               # Gradle settings
├── gradlew / gradlew.bat         # Gradle wrapper
├── gradle/wrapper/               # Gradle wrapper properties
├── local.properties.example      # SDK path template
├── build_apk.bat                 # Build instructions
├── app/
│   ├── build.gradle              # App-level build config (Kotlin + AndroidX)
│   └── src/main/
│       ├── AndroidManifest.xml   # App manifest (INTERNET, NETWORK_STATE perms)
│       ├── kotlin/
│       │   └── com/pegasus/mobile/
│       │       └── MainActivity.kt  # Main activity: WebView + bottom nav
│       └── res/
│           ├── layout/activity_main.xml
│           ├── menu/bottom_nav_menu.xml
│           ├── values/strings.xml
│           ├── values/colors.xml
│           ├── values/themes.xml
│           ├── drawable/ic_launcher.png
│           ├── drawable/ic_dashboard.xml
│           ├── drawable/ic_devices.xml
│           ├── drawable/ic_scan.xml
│           ├── drawable/ic_tools.xml
│           ├── drawable/ic_more.xml
│           └── mipmap-*/ic_launcher.png
```

## Build

### Prerequisites

1. Install [Android SDK command-line tools](https://developer.android.com/studio#command-tools)
2. Extract to `%ANDROID_HOME%\cmdline-tools` (must have `cmdline-tools\latest\bin`)
3. Install platform and build tools:
   ```
   sdkmanager --install "platforms;android-34" "build-tools;34.0.0"
   ```
4. Copy `local.properties.example` to `local.properties` and set `sdk.dir`:
   ```
   copy local.properties.example local.properties
   # Edit local.properties and set: sdk.dir=C:/path/to/android-sdk
   ```

### Build Commands

```cmd
REM Debug APK
.\gradlew assembleDebug

REM Release APK
.\gradlew assembleRelease
```

Output APKs:
- Debug: `app/build/outputs/apk/debug/app-debug.apk`
- Release: `app/build/outputs/apk/release/app-release.apk`

## Install

```cmd
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.pegasus.mobile/.MainActivity
```

## Open Pegasus Dashboard Natively

The app opens the Pegasus dashboard automatically on launch. You can also
trigger it via ADB deep link:

```cmd
adb shell am start -n com.pegasus.mobile/.MainActivity -d "pegasus://pegasus/launch"
```

## Configuration

Edit `app/src/main/res/values/strings.xml` to change the Pegasus base URL:

```xml
<string name="pegasus_base_url">https://your-pegasus-instance.com</string>
```

## License

MIT — For authorized security testing only.
