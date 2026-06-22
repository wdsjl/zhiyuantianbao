# 一键同步：PDF 修复 + 可报院校检索 API + eligible-pool 页面
# 在服务器执行：
#   powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-eligible-pool-search.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/fix-pdf-search-0c75'
$Base = "https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/$Branch"
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

$ServerFiles = @(
  'server/main.py',
  'server/schemas.py',
  'server/pdf_service.py',
  'server/recommend_pool_service.py',
  'server/recommend_service.py'
)

$MiniFiles = @(
  'app.json',
  'pages/volunteer/volunteer.js',
  'pages/schools/schools.js',
  'pages/schools/schools.wxml',
  'utils/membership.js',
  'utils/pdfExport.js',
  'utils/recommendPayload.js',
  'utils/profileSnapshot.js',
  'utils/batchHint.js',
  'pages/profile/profile.js',
  'pages/profile/profile.wxml',
  'pages/home/home.js',
  'pages/home/home.wxml',
  'pages/eligible-pool/eligible-pool.js',
  'pages/eligible-pool/eligible-pool.wxml',
  'pages/eligible-pool/eligible-pool.json',
  'pages/eligible-pool/eligible-pool.wxss'
)

New-Item -ItemType Directory -Path $ServerDir -Force | Out-Null

Write-Host '=== 下载服务器文件 ==='
foreach ($rel in $ServerFiles) {
  $name = Split-Path $rel -Leaf
  $dest = Join-Path $ServerDir $name
  $url = "$Base/$rel"
  Write-Host "  $name"
  curl.exe -fsSL -o $dest $url
  if (-not (Test-Path $dest)) { throw "下载失败: $rel" }
}

Write-Host ''
Write-Host '=== 下载小程序文件（供开发机复制）===' 
foreach ($rel in $MiniFiles) {
  $dest = Join-Path $Root ($rel -replace '/', '\')
  $dir = Split-Path $dest -Parent
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
  $url = "$Base/$rel"
  Write-Host "  $rel"
  curl.exe -fsSL -o $dest $url
}

Write-Host ''
Write-Host '=== Python 导入测试 ==='
Set-Location $ServerDir
python -c "import main; print('import main: OK')"
if ($LASTEXITCODE -ne 0) { throw 'import main 失败' }

Write-Host ''
Write-Host '=== 重启 PM2 ==='
Set-Location $Root
pm2 restart zhiyuan-backend --update-env

Start-Sleep -Seconds 3

Write-Host ''
Write-Host '=== 健康检查 ==='
curl.exe -s "http://127.0.0.1:8001/health"
Write-Host ''

Write-Host ''
Write-Host '=== 批次接口 ==='
curl.exe -s "http://127.0.0.1:8001/api/admission-data/batches?province=河南"
Write-Host ''

Write-Host ''
Write-Host '完成。请用微信开发者工具打开项目并上传小程序。'
Write-Host '检索入口：首页「可报院校检索」或档案保存后点「去检索」。'
