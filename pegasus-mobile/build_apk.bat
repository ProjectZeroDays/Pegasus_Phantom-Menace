@echo off
REM Native APK build script for Pegasus Mobile (Android companion)
REM Requirements (install locally): Android SDK command line tools (
REM cmdline-tools-win-..._latest.zip) + platform + build-tools.
REM Download: https://developer.android.com/studio#command-tools
REM Example (after extracting cmdline-tools and running sdkmanager):
echo.
echo  [1] Download Android SDK command line tools (see README)
echo  [2] Extract to %ANDROID_HOME%\cmdline-tools (must have cmdline-tools\latest\bin)
echo  [3] Run: sdkmanager --install "platforms;android-34" "build-tools;34.0.0"
echo  [4] Ensure ANDROID_HOME and PATH include %ANDROID_HOME%\build-tools\34.0.0
echo.
echo After SDK setup, build with:
echo  javac -classpath android.jar -d build src\com\pegasus\mobile\MainActivity.java
echo  aapt2 compile res -o res.zip
echo  aapt2 link -o base.apk --manifest AndroidManifest.xml -I android.jar -A res.zip
REM Note: APK needs .dex insertion; use d8 or dx, then zipalign + apksigner.
echo  See docs/build_notes.md for full commands.
echo.
echo After build: adb install -r pegasus-mobile.apk
pause
