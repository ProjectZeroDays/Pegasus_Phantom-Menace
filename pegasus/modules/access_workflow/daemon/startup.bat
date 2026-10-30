@echo off
REM Pegasus Phantom Menace v2 - start the daemon in the foreground (dev / login item)
setlocal
set PEGASUS_HOME=%~dp0..
if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" "%~dp0..\pegasus\modules\access_workflow\daemon_service.py" run
) else (
    python "%~dp0..\pegasus\modules\access_workflow\daemon_service.py" run
)
