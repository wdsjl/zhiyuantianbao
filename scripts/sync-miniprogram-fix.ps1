# Sync key miniprogram files from GitHub
# Usage: .\scripts\sync-miniprogram-fix.ps1

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
  'pages/mine/mine.wxss',
  'pages/profile/profile.js',
  'pages/profile/profile.wxml',
  'pages/profile/profile.wxss',
  'pages/profile/profile.json'
)

Write-Host '==> Sync files from GitHub ...' -ForegroundColor Cyan
foreach ($rel in $files) {
  $dest = Join-Path $Root $rel
  $dir = Split-Path -Parent $dest
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $url = "$Base/$($rel -replace '\\','/')"
  Write-Host "  $rel"
  Invoke-WebRequest -Uri $url -OutFile $dest
}

Write-Host ''
Write-Host 'OK: done. Close WeChat DevTools, clear cache, recompile.' -ForegroundColor Green
