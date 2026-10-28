@echo off
REM Native APK build script for Pegasus Mobile (Kotlin Android app)
REM Builds a native Kotlin Android application that loads the Pegasus
REM dashboard inside an embedded WebView with native bottom navigation.
REM
REM Requirements:
REM   - Android SDK command-line tools (cmdline-tools)
REM   - Platform: android-34, Build-Tools: 34.0.0
REM   - JDK 17+
REM   - Gradle wrapper (included: gradlew / gradlew.bat)
REM
REM Setup (first time):
REM   [1] Download Android SDK command line tools
REM   [2] Extract to %ANDROID_HOME%\cmdline-tools (must have cmdline-tools\latest\bin)
REM   [3] Run: sdkmanager --install "platforms;android-34" "build-tools;34.0.0"
REM   [4] Copy local.properties.example to local.properties and set sdk.dir
REM
REM Build:
REM   .\gradlew assembleDebug       (debug APK)
REM   .\gradlew assembleRelease     (release APK)
REM
REM Install (from PC with ADB connected to emulator / device):
REM   adb install -r app/build/outputs/apk/debug/app-debug.apk
REM   adb shell am start -n com.pegasus.mobile/.MainActivity
REM
REM Open Pegasus dashboard natively:
REM   adb shell am start -n com.pegasus.mobile/.MainActivity -d "pegasus://pegasus/launch"
REM
pause
