#requires -Version 5.1
param(
    [string]$Root = "C:\Projects\autonomous-dropshipping-shopify-taskade-app",
    [string]$Message = "chore: pre-jsx-repair snapshot"
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $Root
if (-not (Test-Path .git)) { Write-Host "not a git repo - skipping snapshot" -ForegroundColor Yellow; exit 0 }
git add -A
git commit -m $Message --allow-empty
$sha = (git rev-parse --short HEAD).Trim()
Write-Host "snapshot $sha - roll back with: git reset --hard $sha" -ForegroundColor Green