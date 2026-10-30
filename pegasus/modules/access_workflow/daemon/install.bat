@echo off
REM Pegasus Phantom Menace v2 - service install wrapper
setlocal
set INSTALL_PATH=%~dp0..
if not defined PEGASUS_HOME set "PEGASUS_HOME=%INSTALL_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -InstallPath "%INSTALL_PATH%"
if errorlevel 1 (
    echo.
    echo Install failed. Install NSSM ^(winget install NSSM.NSSM^) or run install-task.bat instead.
)
pause
