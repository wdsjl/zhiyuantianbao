# 艺体专区 + 64志愿 + 横版PDF + 支付openid 热修复同步（服务器 git 不通时用）
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-art-sports-hotfix.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'feature/henan-art-sports-zone-0c75'
$Base = 'https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/' + $Branch
$Root = 'C:\zhiyuantianbao'

$Files = @(
  'server/main.py',
  'server/auth_service.py',
  'server/henan_art_sports_service.py',
  'server/province_rules_service.py',
  'server/pdf_service.py',
  'server/wechat_virtual_pay_service.py',
  'server/recommend_service.py',
  'server/recommend_pool_service.py',
  'server/membership_service.py',
  'server/payment_service.py',
  'server/schemas.py'
)

foreach ($rel in $Files) {
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
Set-Location (Join-Path $Root 'server')
python -c "import main; print('import main: OK')"
if ($LASTEXITCODE -ne 0) { throw 'import main failed - copy files from dev machine E:\zhiyuantianbao instead' }

Write-Host ''
Write-Host '=== restart pm2 ==='
Set-Location $Root
pm2 delete zhiyuan-backend 2>$null
pm2 start ecosystem.config.js
pm2 save
Start-Sleep -Seconds 3

Write-Host ''
Write-Host '=== checks ==='
curl.exe -s http://127.0.0.1:8001/health
Write-Host ''
curl.exe -s http://127.0.0.1:8001/api/payments/wechat/status
Write-Host ''
curl.exe -s 'http://127.0.0.1:8001/api/province-rules/resolve?province=河南&batch=艺术本科批'
Write-Host ''
Write-Host 'SYNC ART SPORTS HOTFIX DONE'
