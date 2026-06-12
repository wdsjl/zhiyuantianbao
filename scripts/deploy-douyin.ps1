# 抖音对接部署脚本 — 在 C:\zhiyuantianbao 以管理员 PowerShell 执行
# 用法: .\scripts\deploy-douyin.ps1

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> 项目目录: $Root" -ForegroundColor Cyan

Write-Host "`n==> 拉取最新代码 (cursor/douyin-integration-0c75)..." -ForegroundColor Cyan
git fetch origin
git reset --hard origin/cursor/douyin-integration-0c75

if (-not (Test-Path "server\bootstrap_secrets.py")) {
    Write-Host "ERROR: server\bootstrap_secrets.py 不存在，代码可能未正确拉取" -ForegroundColor Red
    exit 1
}
Write-Host "OK: bootstrap_secrets.py 已存在" -ForegroundColor Green

Write-Host "`n==> 检查密钥文件..." -ForegroundColor Cyan
node scripts\check-secrets.js
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n密钥检查未通过。请配置 ecosystem.secrets.js 或 server\local.secrets.env 后重试。" -ForegroundColor Yellow
    if (-not (Test-Path "server\local.secrets.env")) {
        Write-Host "可执行: copy server\local.secrets.env.example server\local.secrets.env" -ForegroundColor Yellow
    }
    exit 1
}

Write-Host "`n==> 重启 PM2 后端..." -ForegroundColor Cyan
pm2 delete zhiyuan-backend 2>$null
pm2 start ecosystem.config.js --only zhiyuan-backend --update-env
pm2 save

Start-Sleep -Seconds 3

Write-Host "`n==> 验证 /api/douyin/status ..." -ForegroundColor Cyan
try {
    $status = Invoke-RestMethod "https://api.zntb.lhyun.net/api/douyin/status"
    $status | Format-List

    if ($status.secrets_bootstrap) {
        Write-Host "secrets_bootstrap:" -ForegroundColor Cyan
        $status.secrets_bootstrap | Format-List
    } else {
        Write-Host "WARNING: 响应无 secrets_bootstrap 字段，可能仍在跑旧代码" -ForegroundColor Yellow
    }

    if ($status.enabled -eq $true) {
        Write-Host "`n部署成功：抖音对接已启用" -ForegroundColor Green
        exit 0
    }

    Write-Host "`n部署完成但 enabled=false，请检查密钥配置与 PM2 日志:" -ForegroundColor Yellow
    Write-Host "  pm2 logs zhiyuan-backend --lines 30" -ForegroundColor Yellow
    exit 1
} catch {
    Write-Host "ERROR: 无法访问 API — $_" -ForegroundColor Red
    Write-Host "请检查: pm2 status / pm2 logs zhiyuan-backend" -ForegroundColor Yellow
    exit 1
}
