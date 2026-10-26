# Pegasus Mobile — Native APK Companion

A minimal native Android companion app for Pegasus: Phantom Menace (APK). It shows basic device info, battery, installed package count, and storage — no root, no USB.

## Requirements
- Android SDK command line tools (`sdkmanager`)
- Platforms (`android-34`) + Build-Tools (`build-tools;34.0.0`)
- `javac` (JDK 17 installed) + `d8`/`aapt2`/`zipalign`/`apksigner`

## Build
1. Download SDK command-line tools to `%ANDROID_HOME%\cmdline-tools`.
2. `sdkmanager --install "platforms;android-34" "build-tools;34.0.0"`
3. Build commands (see `build_apk.bat` and full docs):
   ```
   javac -classpath android.jar -d build src/com/pegasus/mobile/MainActivity.java
   aapt2 compile res -o res.zip
   # (d8/dx + zipalign + apksigner complete the APK build)
   ```

## Install (from PC with ADB connected to emulator / device)
```
adb install pegasus-mobile.apk
adb shell am start -n com.pegasus.mobile/.MainActivity
```

## Source
- `src/com/pegasus/mobile/MainActivity.java` — single Activity with device info
- `AndroidManifest.xml` — minimal manifest, `QUERY_ALL_PACKAGES` declared
- `res/values/strings.xml` — app label
- `res/drawable/ic_launcher.png` — app icon (same Pegasus shield)
