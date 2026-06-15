# 在服务器 C:\zhiyuantianbao 执行 — 应用本机复制的离线部署包
# 用法: .\scripts\apply-server-offline.ps1
# 需先将 dist\server-deploy-*.zip 复制到本项目 dist 目录

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$distDir = Join-Path $Root 'dist'
$zips = @(Get-ChildItem -Path $distDir -Filter 'server-deploy-*.zip' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
if (-not $zips.Count) {
    Write-Host "ERROR: 未找到 dist\server-deploy-*.zip" -ForegroundColor Red
    Write-Host "请在本机 E:\zhiyuantianbao 执行 .\scripts\package-server-offline.ps1，" -ForegroundColor Yellow
    Write-Host "再把 dist 目录下的 zip 复制到服务器 C:\zhiyuantianbao\dist\" -ForegroundColor Yellow
    exit 1
}

$zipPath = $zips[0].FullName
Write-Host "==> 使用部署包: $zipPath" -ForegroundColor Cyan

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $Root "server.bak.$stamp"
if (Test-Path 'server') {
    Write-Host "==> 备份当前 server -> $backup" -ForegroundColor Cyan
    Copy-Item -Recurse 'server' $backup
}

Write-Host "==> 解压覆盖 server 目录 ..." -ForegroundColor Cyan
$tempDir = Join-Path $env:TEMP "zhiyuan-server-deploy-$stamp"
if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
Copy-Item -Path (Join-Path $tempDir '*') -Destination (Join-Path $Root 'server') -Recurse -Force
Remove-Item -Recurse -Force $tempDir

$required = @('server\main.py', 'server\score_segment_service.py')
foreach ($file in $required) {
    if (-not (Test-Path $file)) {
        Write-Host "ERROR: 解压后缺少 $file" -ForegroundColor Red
        exit 1
    }
}
Write-Host "OK: score_segment_service.py 已就位" -ForegroundColor Green

Write-Host "`n==> 重启 PM2 ..." -ForegroundColor Cyan
pm2 restart zhiyuan-backend --update-env
if ($LASTEXITCODE -ne 0) {
    pm2 delete zhiyuan-backend 2>$null
    pm2 start ecosystem.config.js --only zhiyuan-backend --update-env
}
pm2 save
Start-Sleep -Seconds 4

Write-Host "`n==> 验证一分一段接口 ..." -ForegroundColor Cyan
try {
    $tables = Invoke-RestMethod 'https://api.zntb.lhyun.net/api/score-segments/tables?province=%E6%B2%B3%E5%8D%97'
    Write-Host "tables 接口正常，记录数: $(@($tables.list).Count)" -ForegroundColor Green
    $lookup = Invoke-RestMethod 'https://api.zntb.lhyun.net/api/score-segments/lookup?province=%E6%B2%B3%E5%8D%97&year=2025&batch=%E6%9C%AC%E7%A7%91%E6%89%B9&subject_type=%E7%89%A9%E7%90%86&score=680'
    Write-Host "lookup 680分 -> 位次 $($lookup.rank)" -ForegroundColor Green
    Write-Host "`n离线部署成功！" -ForegroundColor Green
} catch {
    Write-Host "ERROR: 接口验证失败 — $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "请执行: pm2 logs zhiyuan-backend --lines 40" -ForegroundColor Yellow
    exit 1
}
