# 一键同步小程序关键修复文件（本机 E:\zhiyuantianbao 执行）
# 用法: .\scripts\sync-miniprogram-fix.ps1

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Branch = 'cursor/henan-profile-city-picker-0c75'
$Base = "https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/$Branch"

$files = @(
  'app.json',
  'app.js',
  'utils/request.js',
  'utils/referral.js',
  'utils/applyFlow.js',
  'utils/profileOptions.js',
  'pages/home/home.wxml',
  'pages/home/home.wxss',
  'pages/home/home.js',
  'pages/mine/mine.wxml',
  'pages/profile/profile.js',
  'pages/profile/profile.wxml',
  'pages/profile/profile.wxss'
)

Write-Host "==> 从 GitHub 同步关键文件 ..." -ForegroundColor Cyan
foreach ($rel in $files) {
  $dest = Join-Path $Root $rel
  $dir = Split-Path -Parent $dest
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $url = "$Base/$($rel -replace '\\','/')"
  Write-Host "  $rel"
  Invoke-WebRequest -Uri $url -OutFile $dest
}

Write-Host "`nOK: 同步完成。请关闭微信开发者工具 -> 清缓存 -> 重新编译。" -ForegroundColor Green
Write-Host "若仍点不动，在 Console 执行: wx.getStorageSync('pendingInviteCode')" -ForegroundColor Yellow
