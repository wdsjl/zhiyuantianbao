# Download fresh apply-server-offline.ps1 from GitHub (run on server when local script is broken).
# Usage: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\fetch-apply-script.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/membership-pricing-revamp-0c75'
$Url = 'https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/' + $Branch + '/scripts/apply-server-offline.ps1'
$Dest = 'C:\zhiyuantianbao\scripts\apply-server-offline.ps1'

New-Item -ItemType Directory -Path (Split-Path $Dest) -Force | Out-Null
Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
Write-Host ('Downloaded: ' + $Dest)
Write-Host 'Now run: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\apply-server-offline.ps1'
