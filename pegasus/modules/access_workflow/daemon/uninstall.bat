@echo off
REM Pegasus Phantom Menace v2 - service uninstall wrapper
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
pause
