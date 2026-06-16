# Apply offline server deploy package on Windows server (no git required).
# Usage:
#   1. Copy dist\server-deploy-*.zip to server C:\zhiyuantianbao\dist\
#   2. powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\apply-server-offline.ps1

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$DistDir = Join-Path $Root 'dist'
$ServerDir = Join-Path $Root 'server'
$BackupDir = Join-Path $Root ("backup\server-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))

if (-not (Test-Path $DistDir)) {
  throw "dist folder not found: $DistDir`nCopy server-deploy-*.zip into dist first."
}

$zip = Get-ChildItem $DistDir -Filter 'server-deploy-*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $zip) {
  throw "No server-deploy-*.zip found in $DistDir"
}

Write-Host "Using package: $($zip.FullName)"
Write-Host "Target server dir: $ServerDir"

# 1) Stop API
Write-Host 'Stopping pm2 zhiyuan-backend...'
pm2 stop zhiyuan-backend 2>$null

# 2) Backup current server (code only)
if (Test-Path $ServerDir) {
  New-Item -ItemType Directory -Path (Split-Path $BackupDir) -Force | Out-Null
  Write-Host "Backing up to $BackupDir"
  robocopy $ServerDir $BackupDir /E /XD __pycache__ /XF *.db *.sqlite | Out-Null
}

# 3) Extract zip to temp and copy py files
$Temp = Join-Path $env:TEMP ("zhiyuan-apply-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $Temp | Out-Null
Expand-Archive -Path $zip.FullName -DestinationPath $Temp -Force

# zip root may be flat or contain server/
$Source = $Temp
if (Test-Path (Join-Path $Temp 'server')) {
  $Source = Join-Path $Temp 'server'
}

New-Item -ItemType Directory -Path $ServerDir -Force | Out-Null

# Copy python and related files; never overwrite secrets/db/certs on server
$exclude = @('zhiyuan.db', 'ecosystem.secrets.js')
Get-ChildItem $Source -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($Source.Length).TrimStart('\')
  if ($exclude -contains (Split-Path $rel -Leaf)) { return }
  if ($rel -match '\\certs\\') { return }
  $dest = Join-Path $ServerDir $rel
  $destParent = Split-Path $dest -Parent
  if (-not (Test-Path $destParent)) { New-Item -ItemType Directory -Path $destParent -Force | Out-Null }
  Copy-Item $_.FullName $dest -Force
}

Remove-Item $Temp -Recurse -Force

# 4) Restart
Write-Host 'Starting pm2 zhiyuan-backend...'
Set-Location $Root
pm2 restart zhiyuan-backend --update-env
pm2 save

Write-Host ''
Write-Host 'Deploy done. Verify:'
Write-Host '  pm2 logs zhiyuan-backend --lines 30'
Write-Host '  curl https://api.zntb.lhyun.net/api/membership/plans'
