# 修复微信开发者工具清空 packOptions.ignore 的问题
# 用法: .\scripts\fix-miniprogram-pack-ignore.ps1
# 请先关闭微信开发者工具再执行

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ignoreRules = @(
    @{ type = 'folder'; value = 'server' },
    @{ type = 'folder'; value = 'scripts' },
    @{ type = 'folder'; value = 'dist' },
    @{ type = 'folder'; value = 'database' },
    @{ type = 'folder'; value = '.git' },
    @{ type = 'folder'; value = 'donutAuthorize__' },
    @{ type = 'suffix'; value = '.py' },
    @{ type = 'suffix'; value = '.pyc' },
    @{ type = 'suffix'; value = '.ps1' },
    @{ type = 'suffix'; value = '.sql' },
    @{ type = 'suffix'; value = '.md' },
    @{ type = 'prefix'; value = 'server.bak' },
    @{ type = 'glob'; value = '**/__pycache__/**' }
)

$configPath = Join-Path $Root 'project.config.json'
$privatePath = Join-Path $Root 'project.private.config.json'

if (-not (Test-Path $configPath)) {
    Write-Host "ERROR: 未找到 project.config.json" -ForegroundColor Red
    exit 1
}

$config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $config.packOptions) {
    $config | Add-Member -NotePropertyName packOptions -NotePropertyValue (@{})
}
$config.packOptions.ignore = $ignoreRules
if (-not $config.packOptions.include) {
    $config.packOptions.include = @()
}
$config | ConvertTo-Json -Depth 20 | Set-Content $configPath -Encoding UTF8

$private = [ordered]@{
    description = '本地/打包忽略规则。微信开发者工具可能清空 project.config.json 的 packOptions，此项优先生效。'
    packOptions = @{
        ignore = $ignoreRules
        include = @()
    }
}
($private | ConvertTo-Json -Depth 20) | Set-Content $privatePath -Encoding UTF8

Write-Host "OK: 已写入 packOptions.ignore（project.config.json + project.private.config.json）" -ForegroundColor Green
Write-Host "请重新打开微信开发者工具，并执行：工具 -> 清缓存 -> 全部清除" -ForegroundColor Cyan
