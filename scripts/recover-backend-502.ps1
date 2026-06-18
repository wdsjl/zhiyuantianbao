# 502 紧急恢复：先还原 main.py，再诊断 import 错误。
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\recover-backend-502.ps1

$ErrorActionPreference = 'Continue'
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'
$Main = Join-Path $ServerDir 'main.py'
$Backup = $Main + '.bak'

Write-Host '=== 1. Restore main.py from backup (if exists) ==='
if (Test-Path $Backup) {
  Copy-Item $Backup $Main -Force
  Write-Host 'Restored main.py.bak -> main.py'
} else {
  Write-Host 'No main.py.bak found - skip restore'
}

Write-Host ''
Write-Host '=== 2. Python import test ==='
Set-Location $ServerDir
python -c "import main; print('import main: OK')"
if ($LASTEXITCODE -ne 0) {
  Write-Host ''
  Write-Host 'STILL FAILING. Common missing files on server:'
  Write-Host '  province_rules_service.py'
  Write-Host '  recommend_pool_service.py'
  Write-Host '  recommend_service.py'
  Write-Host '  poster_service.py'
  Write-Host 'Copy them from dev machine E:\zhiyuantianbao\server\ or GitHub branch cursor/fix-pdf-search-0c75'
  exit 1
}

Write-Host ''
Write-Host '=== 3. Restart + local health ==='
Set-Location $Root
pm2 restart zhiyuan-backend --update-env
Start-Sleep -Seconds 2
curl.exe -s http://127.0.0.1:8001/health
Write-Host ''
