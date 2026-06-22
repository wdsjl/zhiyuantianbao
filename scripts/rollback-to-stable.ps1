# 回退到稳定版 v2026.06.18-stable
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\rollback-to-stable.ps1

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$Tag = 'v2026.06.18-stable'
$Branch = 'release/stable-20260618'

Set-Location $Root

Write-Host "=== 回退到稳定版 $Tag ==="

git fetch origin tag $Tag 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "标签未找到，尝试拉取分支 $Branch ..."
  git fetch origin $Branch
  git checkout $Branch
} else {
  git checkout $Tag
}

Write-Host ''
Write-Host '=== import test ==='
Set-Location (Join-Path $Root 'server')
python -c "import main; print('import main: OK')"
if ($LASTEXITCODE -ne 0) {
  Write-Host '警告: import main 失败，请检查 server 目录文件是否完整'
}

Write-Host ''
Write-Host '=== restart pm2 ==='
Set-Location $Root
pm2 delete zhiyuan-backend 2>$null
pm2 start ecosystem.config.js
pm2 save
Start-Sleep -Seconds 3

Write-Host ''
Write-Host '=== health ==='
curl.exe -s http://127.0.0.1:8001/health
Write-Host ''
curl.exe -s https://api.zntb.lhyun.net/api/payments/wechat/status
Write-Host ''
Write-Host ''
Write-Host "回退完成。当前代码版本: $Tag"
Write-Host '小程序请在微信开发者工具重新上传对应版本。'
