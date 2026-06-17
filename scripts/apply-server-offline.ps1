# Apply offline server deploy package on Windows server (ASCII only, no git).
# Usage:
#   1. Copy dist\server-deploy-*.zip to C:\zhiyuantianbao\dist\
#   2. powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\apply-server-offline.ps1

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$DistDir = Join-Path $Root 'dist'
$ServerDir = Join-Path $Root 'server'
$BackupDir = Join-Path $Root ('backup\server-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))

if (-not (Test-Path $DistDir)) {
  throw ('dist folder not found: ' + $DistDir + ' — copy server-deploy-*.zip into dist first.')
}

$zips = @(Get-ChildItem $DistDir -Filter 'server-deploy-*.zip' -ErrorAction SilentlyContinue)
if ($zips.Count -eq 0) {
  throw ('No server-deploy-*.zip found in ' + $DistDir)
}

$zip = $zips | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ('Using package: ' + $zip.FullName)
Write-Host ('Target server dir: ' + $ServerDir)

Write-Host 'Stopping pm2 zhiyuan-backend...'
pm2 stop zhiyuan-backend 2>$null

if (Test-Path $ServerDir) {
  $backupParent = Split-Path $BackupDir -Parent
  if (-not (Test-Path $backupParent)) {
    New-Item -ItemType Directory -Path $backupParent -Force | Out-Null
  }
  Write-Host ('Backing up to ' + $BackupDir)
  robocopy $ServerDir $BackupDir /E /XD __pycache__ /XF *.db *.sqlite | Out-Null
}

$Temp = Join-Path $env:TEMP ('zhiyuan-apply-' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $Temp -Force | Out-Null
Expand-Archive -Path $zip.FullName -DestinationPath $Temp -Force

$Source = $Temp
if (Test-Path (Join-Path $Temp 'server')) {
  $Source = Join-Path $Temp 'server'
}

if (-not (Test-Path $Source)) {
  throw ('Invalid zip layout: server folder not found inside package.')
}

New-Item -ItemType Directory -Path $ServerDir -Force | Out-Null

$excludeNames = @('zhiyuan.db', 'ecosystem.secrets.js')
Get-ChildItem $Source -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($Source.Length).TrimStart('\')
  $leaf = Split-Path $rel -Leaf
  if ($excludeNames -contains $leaf) { return }
  if ($rel -match '\\certs\\') { return }
  $dest = Join-Path $ServerDir $rel
  $destParent = Split-Path $dest -Parent
  if (-not (Test-Path $destParent)) {
    New-Item -ItemType Directory -Path $destParent -Force | Out-Null
  }
  Copy-Item $_.FullName $dest -Force
}

Remove-Item $Temp -Recurse -Force

Write-Host 'Starting pm2 zhiyuan-backend...'
Set-Location $Root
pm2 restart zhiyuan-backend --update-env
pm2 save

Write-Host ''
Write-Host 'Deploy done.'
Write-Host 'Verify:'
Write-Host '  pm2 logs zhiyuan-backend --lines 40'
Write-Host '  curl https://api.zntb.lhyun.net/api/payments/wechat/status'
