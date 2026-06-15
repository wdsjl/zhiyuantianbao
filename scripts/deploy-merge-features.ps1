# 合并功能部署脚本 — 在 C:\zhiyuantianbao 以管理员 PowerShell 执行
# 用法: .\scripts\deploy-merge-features.ps1
# 包含：一分一段查询、可报院校池、招生公告后台、档案同步等

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> 项目目录: $Root" -ForegroundColor Cyan

$Branch = 'cursor/merge-all-features-0c75'
Write-Host "`n==> 拉取最新代码 ($Branch)..." -ForegroundColor Cyan
try {
    git fetch origin $Branch
    git checkout $Branch 2>$null
    git reset --hard "origin/$Branch"
} catch {
    Write-Host "ERROR: git 拉取失败 — $_" -ForegroundColor Red
    Write-Host "若服务器无法连接 GitHub，请在本机 E:\zhiyuantianbao 打包 server 目录，复制到服务器后重试本脚本（跳过 git 步骤）。" -ForegroundColor Yellow
    exit 1
}

$requiredFiles = @(
    'server\main.py',
    'server\score_segment_service.py',
    'server\recommend_pool_service.py'
)
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "ERROR: 缺少 $file，代码可能未正确拉取" -ForegroundColor Red
        exit 1
    }
}
Write-Host "OK: 关键后端文件已存在" -ForegroundColor Green

Write-Host "`n==> 重启 PM2 后端..." -ForegroundColor Cyan
pm2 restart zhiyuan-backend --update-env
if ($LASTEXITCODE -ne 0) {
    pm2 delete zhiyuan-backend 2>$null
    pm2 start ecosystem.config.js --only zhiyuan-backend --update-env
}
pm2 save

Start-Sleep -Seconds 4

Write-Host "`n==> 验证一分一段接口..." -ForegroundColor Cyan
try {
    $tables = Invoke-RestMethod "https://api.zntb.lhyun.net/api/score-segments/tables?province=%E6%B2%B3%E5%8D%97"
    $count = @($tables.list).Count
    Write-Host "tables 接口正常，返回 $count 条记录" -ForegroundColor Green

    $lookup = Invoke-RestMethod "https://api.zntb.lhyun.net/api/score-segments/lookup?province=%E6%B2%B3%E5%8D%97&year=2025&batch=%E6%9C%AC%E7%A7%91%E6%89%B9&subject_type=%E7%89%A9%E7%90%86&score=680"
    if ($lookup.rank) {
        Write-Host "lookup 接口正常，680分对应位次: $($lookup.rank)" -ForegroundColor Green
        Write-Host "`n部署成功：一分一段查询已启用" -ForegroundColor Green
        exit 0
    }
    Write-Host "lookup 返回无 rank，请检查数据库是否已导入河南一分一段表" -ForegroundColor Yellow
    exit 1
} catch {
    $detail = $_.Exception.Message
    if ($detail -match '404|Not Found') {
        Write-Host "ERROR: 一分一段接口仍返回 404，说明 PM2 仍在跑旧代码" -ForegroundColor Red
        Write-Host "请确认 git log -1 为 5d29404 或更新，并执行: pm2 logs zhiyuan-backend --lines 30" -ForegroundColor Yellow
    } else {
        Write-Host "ERROR: 验证失败 — $detail" -ForegroundColor Red
    }
    exit 1
}
