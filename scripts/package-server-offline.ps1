# Package server code for offline deploy (run on dev PC with latest code).
# Output: dist\server-deploy-YYYYMMDD-HHmmss.zip

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ServerDir = Join-Path $Root 'server'
$DistDir = Join-Path $Root 'dist'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$ZipName = "server-deploy-$Stamp.zip"
$ZipPath = Join-Path $DistDir $ZipName
$Stage = Join-Path $env:TEMP "zhiyuan-server-stage-$Stamp"

if (-not (Test-Path $ServerDir)) {
  throw "server folder not found: $ServerDir"
}

Write-Host "Packaging server from: $ServerDir"

if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage | Out-Null
New-Item -ItemType Directory -Path $DistDir -Force | Out-Null

# Copy server code; exclude runtime data and caches
robocopy $ServerDir $Stage /E /XD __pycache__ .pytest_cache certs logs /XF *.db *.sqlite *.log | Out-Null

# Include root ecosystem config (pm2)
foreach ($file in @('ecosystem.config.js', 'ecosystem.secrets.example.js')) {
  $src = Join-Path $Root $file
  if (Test-Path $src) { Copy-Item $src $Stage -Force }
}

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $Stage '*') -DestinationPath $ZipPath -Force
Remove-Item $Stage -Recurse -Force

Write-Host ''
Write-Host "Created: $ZipPath"
Write-Host 'Next: copy this zip to server, then run scripts\apply-server-offline.ps1'
