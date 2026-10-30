@echo off
REM Pegasus Phantom Menace v2 - boot-time scheduled task (no NSSM required)
setlocal
set INSTALL_PATH=%~dp0..
set TASK=PegasusDaemon
set RUNNER="%INSTALL_PATH%\launchers\pegasus.bat"

schtasks /Create /TN "%TASK%" /SC ONSTART /RL HIGHEST /TR "%RUNNER% daemon run" /F
if errorlevel 1 (
    echo Registration failed - run this script as Administrator.
    pause
    exit /b 1
)
schtasks /Run /TN "%TASK%"
echo Task '%TASK%' registered. Remove with: schtasks /Delete /TN %TASK% /F
pause
