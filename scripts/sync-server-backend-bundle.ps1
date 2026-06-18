# 一次性同步 main.py 所需的全部服务端文件（避免逐个缺函数导致 502）。
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-server-backend-bundle.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/fix-payment-500-0c75'
$Base = 'https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/' + $Branch
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

$ServerFiles = @(
  'server/main.py',
  'server/auth_service.py',
  'server/payment_service.py',
  'server/pdf_service.py',
  'server/province_rules_service.py',
  'server/recommend_pool_service.py',
  'server/recommend_service.py',
  'server/schemas.py',
  'server/poster_service.py',
  'server/referral_service.py',
  'server/membership_service.py',
  'server/wechat_virtual_pay_service.py',
  'server/bean_service.py',
  'server/admin_views.py',
  'server/wechat_msg_push_service.py',
  'server/assets/referral/poster_template.png',
  'server/assets/fonts/WenQuanYiMicroHei.ttf'
)

New-Item -ItemType Directory -Path $ServerDir -Force | Out-Null

foreach ($rel in $ServerFiles) {
  $dest = Join-Path $Root ($rel -replace '/', '\')
  $dir = Split-Path $dest -Parent
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
  if (Test-Path $dest) {
    Copy-Item $dest ($dest + '.bak') -Force
  }
  $url = $Base + '/' + $rel
  Write-Host ('Downloading ' + $rel + ' ...')
  curl.exe -fsSL -o $dest $url
  if (-not (Test-Path $dest)) { throw ('Download failed: ' + $rel) }
}

Write-Host ''
Write-Host '=== import test ==='
Set-Location $ServerDir
python -c "import main; print('import main: OK')"
if ($LASTEXITCODE -ne 0) { throw 'import main failed - copy files from dev machine E:\zhiyuantianbao instead' }

Write-Host ''
Write-Host '=== restart pm2 ==='
Set-Location $Root
pm2 restart zhiyuan-backend --update-env
Start-Sleep -Seconds 3

Write-Host ''
Write-Host '=== health check ==='
curl.exe -s http://127.0.0.1:8001/health
Write-Host ''
curl.exe -s https://api.zntb.lhyun.net/health
Write-Host ''
curl.exe -s https://api.zntb.lhyun.net/api/payments/wechat/status
Write-Host ''
