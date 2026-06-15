# 在本机 E:\zhiyuantianbao 执行 — 打包 server 目录供服务器离线部署
# 用法: .\scripts\package-server-offline.ps1
# 将生成的 zip 通过远程桌面复制到服务器后，运行 scripts\apply-server-offline.ps1

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Branch = 'cursor/merge-all-features-0c75'
Write-Host "==> 当前目录: $Root" -ForegroundColor Cyan

$branchName = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branchName -ne $Branch) {
    Write-Host "切换到 $Branch ..." -ForegroundColor Yellow
    git fetch origin $Branch
    git checkout $Branch
    git pull origin $Branch
}

$commit = (git rev-parse --short HEAD).Trim()
$outDir = Join-Path $Root 'dist'
$zipPath = Join-Path $outDir "server-deploy-$commit.zip"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Write-Host "==> 打包 server 目录 (commit $commit) ..." -ForegroundColor Cyan
Compress-Archive -Path (Join-Path $Root 'server\*') -DestinationPath $zipPath -Force

$bundlePath = Join-Path $outDir "merge-features-$commit.bundle"
Write-Host "==> 生成 git bundle (可选，服务器可离线 git fetch) ..." -ForegroundColor Cyan
git bundle create $bundlePath "origin/$Branch"

Write-Host "`n已生成:" -ForegroundColor Green
Write-Host "  ZIP:    $zipPath"
Write-Host "  Bundle: $bundlePath"
Write-Host "`n下一步:" -ForegroundColor Cyan
Write-Host "  1. 远程桌面登录服务器，把 ZIP 复制到 C:\zhiyuantianbao\dist\"
Write-Host "  2. 在服务器执行: .\scripts\apply-server-offline.ps1"
