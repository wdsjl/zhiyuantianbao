# Sync virtual-pay deliver-notify server files from GitHub (no git, no zip).
# Run on SERVER: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-server-deliver-notify.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/membership-pricing-revamp-0c75'
$Base = 'https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/' + $Branch
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

$Files = @(
  'server/main.py',
  'server/wechat_msg_push_service.py',
  'server/wechat_virtual_pay_service.py',
  'server/membership_service.py',
  'server/bean_service.py',
  'server/payment_service.py',
  'server/admin_views.py',
  'scripts/repair-virtual-order.ps1',
  'scripts/diagnose-virtual-pay.ps1',
  'scripts/fetch-repair-script.ps1'
)

New-Item -ItemType Directory -Path $ServerDir -Force | Out-Null
$ScriptDir = Join-Path $Root 'scripts'
New-Item -ItemType Directory -Path $ScriptDir -Force | Out-Null

foreach ($rel in $Files) {
  $url = $Base + '/' + $rel
  $name = Split-Path $rel -Leaf
  if ($rel.StartsWith('scripts/')) {
    $dest = Join-Path $ScriptDir $name
  } else {
    $dest = Join-Path $ServerDir $name
  }
  Write-Host ('Downloading ' + $name + ' ...')
  curl.exe -fsSL -o $dest $url
  if (-not (Test-Path $dest)) {
    throw ('Download failed: ' + $rel)
  }
}

Write-Host ''
Write-Host 'Files updated. Restarting pm2...'
Set-Location $Root
pm2 restart zhiyuan-backend --update-env
pm2 save

Write-Host ''
Write-Host 'Verify GET handler (should match api_route deliver-notify):'
Select-String -Path (Join-Path $ServerDir 'main.py') -Pattern 'deliver-notify' | ForEach-Object { $_.Line }

Write-Host ''
Write-Host 'Test URL (expect NOT Method Not Allowed):'
Write-Host 'curl.exe -s "https://api.zntb.lhyun.net/api/payments/virtual/deliver-notify?signature=test&timestamp=1&nonce=1&echostr=hello"'
