# Sync membership revamp files from GitHub (no git required).
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\sync-membership-revamp.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/membership-pricing-revamp-0c75'
$Base = "https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/$Branch"

$Files = @(
  'app.js',
  'utils/referral.js',
  'utils/planCatalog.js',
  'utils/reportBean.js',
  'utils/membership.js',
  'pages/membership/membership.js',
  'pages/membership/membership.wxml',
  'pages/home/home.wxml',
  'pages/mine/mine.wxml',
  'pages/personality/personality.js',
  'pages/personality/personality.wxml',
  'pages/student-report/student-report.js',
  'pages/student-report/student-report.wxml'
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Sync from branch: $Branch"
Write-Host "Project root: $Root"
Write-Host ''

foreach ($rel in $Files) {
  $url = "$Base/$($rel -replace '\\','/')"
  $dest = Join-Path $Root ($rel -replace '/','\')
  $dir = Split-Path -Parent $dest
  if ($dir -and -not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  Write-Host "Downloading $rel ..."
  Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
}

Write-Host ''
Write-Host 'Done. Verify:'
Write-Host '  Select-String -Path pages\membership\membership.wxml -Pattern "星鼎豆"'
Write-Host '  (should return nothing)'
Write-Host '  Select-String -Path utils\planCatalog.js -Pattern "298"'
Write-Host 'Then: WeChat DevTools -> Clear cache -> Compile'
