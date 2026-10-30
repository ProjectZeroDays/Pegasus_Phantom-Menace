# Pegasus Phantom Menace v2 - service removal (NSSM and/or scheduled task)
# Run elevated.

param(
    [string]$ServiceName = "PegasusDaemon",
    [string]$TaskName = "PegasusDaemon",
    [switch]$KeepFiles
)

$ErrorActionPreference = "Continue"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator rights are required."
}

$nssm = (Get-Command nssm.exe -ErrorAction SilentlyContinue)
if (-not $nssm) {
    $nssm = @("$env:ProgramFiles\nssm\nssm.exe", "$env:ChocolateyInstall\bin\nssm.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}

if ($nssm -and (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
    & $nssm stop $ServiceName
    & $nssm remove $ServiceName confirm
    Write-Host "Service '$ServiceName' removed." -ForegroundColor Green
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Scheduled task '$TaskName' removed." -ForegroundColor Green
}

if (-not $KeepFiles) {
    $installPath = Join-Path $env:ProgramFiles "Pegasus Phantom Menace v2"
    if (Test-Path $installPath) {
        $running = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$installPath*" }
        $running | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        Remove-Item $installPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Removed $installPath" -ForegroundColor Green
    }
}
