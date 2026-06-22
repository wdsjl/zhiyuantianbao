# 在服务器本机同步专家版物理/历史表的保研率与招生章程（绕过 Nginx 60s 超时）
# 用法:
#   powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-expert-profiles.ps1 -PhysicsFile "D:\数据\物理.xlsx"
#   powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-expert-profiles.ps1 -HistoryFile "D:\数据\历史.xlsx"
# 两个文件都传:
#   powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-expert-profiles.ps1 -PhysicsFile "...\物理.xlsx" -HistoryFile "...\历史.xlsx"

param(
  [string]$PhysicsFile = '',
  [string]$HistoryFile = ''
)

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

if (-not $PhysicsFile -and -not $HistoryFile) {
  Write-Host '请至少指定 -PhysicsFile 或 -HistoryFile'
  Write-Host '示例: -PhysicsFile "D:\物理.xlsx" -HistoryFile "D:\历史.xlsx"'
  exit 1
}

Set-Location $ServerDir

function Sync-OneFile([string]$Path) {
  if (-not (Test-Path $Path)) { throw "文件不存在: $Path" }
  $name = Split-Path $Path -Leaf
  Write-Host "=== 同步 $name ==="
  $py = @"
from pathlib import Path
from import_service import run_sync_expert_school_profiles
content = Path(r'$($Path.Replace("'", "''"))').read_bytes()
result = run_sync_expert_school_profiles('$($name.Replace("'", "''"))', content)
print('完成: 院校', result['total_count'], '所, 成功', result['success_count'], '所')
print('含章程', result.get('schools_with_regulation', 0), '所, 含保研率', result.get('schools_with_postgraduate_rate', 0), '所')
"@
  python -c $py
  if ($LASTEXITCODE -ne 0) { throw "同步失败: $name" }
}

if ($PhysicsFile) { Sync-OneFile $PhysicsFile }
if ($HistoryFile) { Sync-OneFile $HistoryFile }

Write-Host ''
Write-Host 'SYNC EXPERT PROFILES DONE'
Write-Host '可在后台「导入日志」查看 school_profiles_from_expert 记录'
