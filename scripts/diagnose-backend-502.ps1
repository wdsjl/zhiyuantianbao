# Diagnose 502 Bad Gateway after pm2 restart.
# Usage: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\diagnose-backend-502.ps1

$ErrorActionPreference = 'Continue'
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

Write-Host '=== 1. Required files ==='
$Required = @(
  'main.py',
  'province_rules_service.py',
  'membership_service.py',
  'wechat_virtual_pay_service.py'
)
foreach ($name in $Required) {
  $path = Join-Path $ServerDir $name
  if (Test-Path $path) {
    Write-Host ('OK  ' + $name)
  } else {
    Write-Host ('MISSING  ' + $name)
  }
}

Write-Host ''
Write-Host '=== 2. Python import test ==='
Set-Location $ServerDir
python -c "import main; print('import main: OK')"
if ($LASTEXITCODE -ne 0) {
  Write-Host 'import main FAILED - see traceback above'
}

Write-Host ''
Write-Host '=== 3. Local health (127.0.0.1:8001) ==='
try {
  $health = curl.exe -s -m 5 "http://127.0.0.1:8001/health"
  if ($health) { Write-Host $health } else { Write-Host 'no response on :8001' }
} catch {
  Write-Host 'curl local health failed'
}

Write-Host ''
Write-Host '=== 4. PM2 status + last logs ==='
Set-Location $Root
pm2 describe zhiyuan-backend
Write-Host ''
pm2 logs zhiyuan-backend --lines 40 --nostream

Write-Host ''
Write-Host 'If province_rules_service.py is MISSING, copy it from branch cursor/membership-pricing-revamp-0c75'
Write-Host 'Then: pm2 restart zhiyuan-backend --update-env'
