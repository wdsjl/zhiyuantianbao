# 回归锁：已修复功能不得回退
# 本地/服务器: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\verify-regression-locks.ps1

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'
$ApiBase = 'https://api.zntb.lhyun.net'

Write-Host '=== 1. Unit tests (regression locks) ==='
Set-Location $ServerDir
python -m unittest test_regression_locks.py test_membership_pricing.py -v
if ($LASTEXITCODE -ne 0) { throw 'Regression unit tests FAILED' }

Write-Host ''
Write-Host '=== 2. Production API smoke ==='
$health = curl.exe -s -m 10 "$ApiBase/health"
Write-Host "health: $health"
if ($health -notmatch 'ok') { throw 'health check failed' }

$status = curl.exe -s -m 10 "$ApiBase/api/province-rules/status"
Write-Host "province-rules/status: $status"
if ($status -notmatch '"total_slots":48') { throw 'Henan sample must be total_slots=48' }

$pdf = curl.exe -s -m 10 "$ApiBase/api/membership/permissions/pdf_export/check?user_id=95"
Write-Host "pdf_export/check: $pdf"
if ($pdf -notmatch '"allowed":true') { Write-Host 'WARN: user 95 pdf_export not allowed (check membership)' }

$pay = curl.exe -s -m 10 "$ApiBase/api/payments/wechat/status"
Write-Host "payments/wechat/status: $pay"
if ($pay -notmatch '"enabled":true') { throw 'virtual pay must be enabled' }
if ($pay -notmatch '"product_id":"xdptk"') { throw 'trial product_id must be xdptk' }
if ($pay -notmatch '"product_id":"xdbjk"') { throw 'premium product_id must be xdbjk' }

Write-Host ''
Write-Host 'ALL REGRESSION LOCKS PASSED'
