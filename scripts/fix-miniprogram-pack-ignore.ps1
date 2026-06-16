# 修复 project.config.json 语法错误 / packOptions.ignore 被清空
# 用法: .\scripts\fix-miniprogram-pack-ignore.ps1
# 请先关闭微信开发者工具再执行

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

$templatePath = Join-Path $Root 'scripts\project.config.template.json'
$configPath = Join-Path $Root 'project.config.json'
$privatePath = Join-Path $Root 'project.private.config.json'

if (-not (Test-Path $templatePath)) {
    Write-Host "ERROR: 未找到 scripts\project.config.template.json" -ForegroundColor Red
    exit 1
}

$configText = Get-Content $templatePath -Raw -Encoding UTF8
try {
    $null = $configText | ConvertFrom-Json
} catch {
    Write-Host "ERROR: 模板 JSON 无效 — $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Utf8NoBom -Path $configPath -Content $configText

$privateText = @'
{
  "description": "本地/打包忽略规则。微信开发者工具可能清空 project.config.json 的 packOptions，此项优先生效。",
  "packOptions": {
    "ignore": [
      { "type": "folder", "value": "server" },
      { "type": "folder", "value": "scripts" },
      { "type": "folder", "value": "dist" },
      { "type": "folder", "value": "database" },
      { "type": "folder", "value": ".git" },
      { "type": "folder", "value": "donutAuthorize__" },
      { "type": "suffix", "value": ".py" },
      { "type": "suffix", "value": ".pyc" },
      { "type": "suffix", "value": ".ps1" },
      { "type": "suffix", "value": ".sql" },
      { "type": "suffix", "value": ".md" },
      { "type": "prefix", "value": "server.bak" },
      { "type": "glob", "value": "**/__pycache__/**" }
    ],
    "include": []
  }
}
'@

Write-Utf8NoBom -Path $privatePath -Content $privateText

Write-Host "OK: 已用模板覆盖 project.config.json（UTF-8 无 BOM）" -ForegroundColor Green
Write-Host "OK: 已写入 project.private.config.json" -ForegroundColor Green
Write-Host "请重新打开微信开发者工具，并执行：工具 -> 清缓存 -> 全部清除" -ForegroundColor Cyan
