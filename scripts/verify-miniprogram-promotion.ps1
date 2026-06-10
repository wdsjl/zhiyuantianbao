# 在微信开发者工具所在电脑上运行，确认小程序源码是否包含推广入口
$root = if ($args[0]) { $args[0] } else { "C:\zhiyuantianbao" }
Write-Host "检查目录: $root"

$files = @(
  "pages\mine\mine.wxml",
  "pages\home\home.wxml",
  "pages\promotion\promotion.js",
  "app.json",
  "utils\miniappVersion.js"
)

foreach ($rel in $files) {
  $path = Join-Path $root $rel
  if (Test-Path $path) {
    Write-Host "[OK] $rel"
  } else {
    Write-Host "[缺失] $rel" -ForegroundColor Red
  }
}

$mine = Join-Path $root "pages\mine\mine.wxml"
if (Test-Path $mine) {
  $text = Get-Content $mine -Raw -Encoding UTF8
  if ($text -match "达人推广中心") {
    Write-Host "[OK] mine.wxml 含「达人推广中心」" -ForegroundColor Green
  } else {
    Write-Host "[旧版] mine.wxml 没有推广入口，请 git reset 到最新分支" -ForegroundColor Red
  }
}

$ver = Join-Path $root "utils\miniappVersion.js"
if (Test-Path $ver) {
  Select-String -Path $ver -Pattern "BUILD_TAG"
}

Write-Host ""
Write-Host "微信开发者工具请打开此目录: $root"
Write-Host "清缓存后编译，我的页底部应显示: 小程序版本 promotion-p3-20250605"
