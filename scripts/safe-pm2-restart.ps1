# 安全重启后端：先备份 secrets、校验语法，再启动并检查虚拟支付状态
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\safe-pm2-restart.ps1

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$BackupDir = Join-Path $Root 'backup'
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if (-not (Test-Path $BackupDir)) {
  New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

foreach ($name in @('ecosystem.secrets.js', 'ecosystem.config.js')) {
  $src = Join-Path $Root $name
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $BackupDir "$name.$Timestamp.bak") -Force
    Write-Host "Backed up $name"
  }
}

& (Join-Path $Root 'scripts\validate-ecosystem-secrets.ps1')

Set-Location $Root
pm2 delete zhiyuan-backend 2>$null
pm2 start ecosystem.config.js
pm2 save
Start-Sleep -Seconds 3

$status = curl.exe -s -m 10 'http://127.0.0.1:8001/api/payments/wechat/status'
Write-Host "payment status: $status"
if ($status -notmatch '"enabled":true' -or $status -notmatch '"secret_configured":true') {
  throw '虚拟支付未就绪，已中止。请检查 ecosystem.secrets.js 后重试，勿继续部署。'
}

$health = curl.exe -s -m 10 'http://127.0.0.1:8001/health'
Write-Host "health: $health"
Write-Host 'SAFE PM2 RESTART PASSED'
