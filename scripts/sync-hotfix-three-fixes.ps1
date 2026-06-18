# Hotfix: province volunteer slots + PDF permissions + school search filters.
# Run on SERVER: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-hotfix-three-fixes.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/membership-pricing-revamp-0c75'
$Base = 'https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/' + $Branch
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

$ServerFiles = @(
  'server/province_rules_service.py',
  'server/main.py',
  'server/membership_service.py',
  'server/schemas.py',
  'server/wechat_virtual_pay_service.py'
)

$MiniFiles = @(
  'pages/volunteer/volunteer.js',
  'pages/schools/schools.js'
)

New-Item -ItemType Directory -Path $ServerDir -Force | Out-Null

foreach ($rel in $ServerFiles) {
  $name = Split-Path $rel -Leaf
  $dest = Join-Path $ServerDir $name
  $url = $Base + '/' + $rel
  Write-Host ('Downloading ' + $name + ' ...')
  curl.exe -fsSL -o $dest $url
  if (-not (Test-Path $dest)) { throw ('Download failed: ' + $rel) }
}

foreach ($rel in $MiniFiles) {
  $dest = Join-Path $Root ($rel -replace '/', '\')
  $dir = Split-Path $dest -Parent
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
  $url = $Base + '/' + $rel
  Write-Host ('Downloading ' + $rel + ' ...')
  curl.exe -fsSL -o $dest $url
  if (-not (Test-Path $dest)) { throw ('Download failed: ' + $rel) }
}

Write-Host ''
Write-Host 'Restarting pm2...'
Set-Location $Root
pm2 restart zhiyuan-backend --update-env
pm2 save

Write-Host ''
Write-Host 'Verify province rules (Henan should be 48):'
Write-Host 'curl.exe -s "https://api.zntb.lhyun.net/api/province-rules/resolve?province=河南&batch=本科批"'
Write-Host ''
Write-Host 'Mini program: recompile after copying pages/volunteer and pages/schools.'
