@echo off
REM Pegasus Mobile v2.1 — Native Kotlin APK build (enhanced)
REM Builds app/build/outputs/apk/debug/app-debug.apk
REM Build-tools target: 34.0.0 | SDK: android-34 | JDK: 17+

setlocal

if not defined ANDROID_HOME (
    echo ERROR: ANDROID_HOME not set.
    echo Set to SDK root and ensure cmdline-tools\latest\bin is on PATH.
    exit /b 1
)

if not defined JAVA_HOME (
    echo WARNING: JAVA_HOME not set. Ensure JDK 17+ is available.
)

echo === Pegasus Mobile APK Build v2.1 ===
echo.

echo Checking Gradle wrapper...
if not exist gradlew.bat (
    echo ERROR: gradlew.bat not found. Run from pegasus-mobile directory.
    exit /b 1
)

echo Cleaning previous outputs ...
call .\gradlew clean --quiet 2>nul

echo Building DEBUG APK ...
call .\gradlew assembleDebug

if errorlevel 1 (
    echo BUILD FAILED. See build output.
    exit /b 1
)

echo.
echo Build output:
for %%f in (app\build\outputs\apk\debug\app-debug.apk) do (
    if exist %%f (
        echo  SUCCESS: %%f  (%%~zf bytes)
    ) else (
        echo  APK not produced at expected path.
    )
)

echo.
echo To install (with ADB):
echo   adb install -r app\build\outputs\apk\debug\app-debug.apk
pause
endlocal
