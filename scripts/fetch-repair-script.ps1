# Download repair + diagnose scripts via curl (avoids Invoke-WebRequest index errors on PS 5.1).
# Usage: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\fetch-repair-script.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/membership-pricing-revamp-0c75'
$Base = 'https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/' + $Branch + '/scripts'
$Root = 'C:\zhiyuantianbao'
$ScriptDir = Join-Path $Root 'scripts'

New-Item -ItemType Directory -Path $ScriptDir -Force | Out-Null

$Names = @(
  'repair-virtual-order.ps1',
  'diagnose-virtual-pay.ps1',
  'sync-server-deliver-notify.ps1'
)

foreach ($name in $Names) {
  $dest = Join-Path $ScriptDir $name
  $url = $Base + '/' + $name
  Write-Host ('Downloading ' + $name + ' ...')
  curl.exe -fsSL -o $dest $url
  if (-not (Test-Path $dest)) {
    throw ('Download failed: ' + $name)
  }
}

Write-Host ''
Write-Host 'OK. Next:'
Write-Host '  powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\repair-virtual-order.ps1 M2026061120213195 M2026061020574395'
