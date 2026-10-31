# Pegasus Phantom Menace v2 - service installation (NSSM)
# Run elevated from the installer or by hand:
#   powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [string]$InstallPath = "$env:ProgramFiles\Pegasus Phantom Menace v2",
    [string]$ServiceName = "PegasusDaemon",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 5050
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrator rights are required."
    }
}

Assert-Admin

$python = Join-Path $InstallPath ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = (Get-Command python.exe -ErrorAction Stop).Source }
$daemon = Join-Path $InstallPath "pegasus\modules\access_workflow\daemon_service.py"
if (-not (Test-Path $daemon)) { throw "daemon_service.py not found at $daemon" }

$nssm = (Get-Command nssm.exe -ErrorAction SilentlyContinue)
if (-not $nssm) {
    $candidates = @(
        "$InstallPath\daemon\nssm.exe",
        "$env:ProgramFiles\nssm\nssm.exe",
        "$env:ChocolateyInstall\bin\nssm.exe"
    )
    $nssm = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $nssm) { throw "NSSM not found. Install it (winget install NSSM.NSSM) or use the scheduled task." }

$logDir = Join-Path $env:LOCALAPPDATA "Pegasus\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

& $nssm install $ServiceName $python $daemon --host $HostAddress --port $Port
& $nssm set $ServiceName AppDirectory $InstallPath
& $nssm set $ServiceName DisplayName "Pegasus Phantom Menace Daemon"
& $nssm set $ServiceName Description "Pegasus Phantom Menace dashboard daemon"
& $nssm set $ServiceName Start SERVICE_AUTO_START
& $nssm set $ServiceName AppStdout "$logDir\daemon.out.log"
& $nssm set $ServiceName AppStderr "$logDir\daemon.err.log"
& $nssm set $ServiceName AppRotateFiles 1
& $nssm set $ServiceName AppRotateBytes 1048576
& $nssm start $ServiceName

Write-Host "Service '$ServiceName' installed and started on http://${HostAddress}:$Port/" -ForegroundColor Green
