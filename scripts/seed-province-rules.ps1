# Seed province_rules table and verify Henan=48.
# Usage: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\seed-province-rules.ps1

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

Set-Location $ServerDir
python -c "from province_rules_service import ensure_province_rules_seeded, resolve_volunteer_slots, count_province_rules_in_db; ensure_province_rules_seeded(); print(count_province_rules_in_db()); print(resolve_volunteer_slots('河南', '本科批'))"

Write-Host ''
Write-Host 'Restarting pm2...'
Set-Location $Root
pm2 restart zhiyuan-backend --update-env

Write-Host ''
Write-Host 'Test (use percent-encoded URL to avoid PowerShell encoding issues):'
Write-Host 'curl.exe -s "https://api.zntb.lhyun.net/api/province-rules/status"'
Write-Host 'curl.exe -s "https://api.zntb.lhyun.net/api/province-rules/resolve?province=%E6%B2%B3%E5%8D%97&batch=%E6%9C%AC%E7%A7%91%E6%89%B9"'
