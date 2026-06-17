# Repair virtual-pay order: grant membership + notify WeChat shipped.
# Usage:
#   powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\repair-virtual-order.ps1 M2026061120213195
#   powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\repair-virtual-order.ps1 M2026061120213195 M2026061020574395

param(
  [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
  [string[]]$OrderNos
)

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

if (-not (Test-Path (Join-Path $Root 'ecosystem.config.js'))) {
  throw ('ecosystem.config.js not found: ' + $Root)
}

Write-Host 'Loading env from ecosystem.config.js ...'
$envJson = node -e "const c=require('./ecosystem.config.js'); process.stdout.write(JSON.stringify(c.apps[0].env||{}));"
if (-not $envJson) {
  throw 'Failed to read env from ecosystem.config.js'
}

$envObj = $envJson | ConvertFrom-Json
$envObj.PSObject.Properties | ForEach-Object {
  $name = $_.Name
  $value = [string]$_.Value
  if ($value) {
    Set-Item -Path ('Env:' + $name) -Value $value
  }
}

Set-Location $ServerDir

foreach ($orderNo in $OrderNos) {
  if (-not $orderNo) { continue }
  Write-Host ('Repairing order: ' + $orderNo)
  python -c "from wechat_virtual_pay_service import repair_virtual_order; print(repair_virtual_order('$orderNo'))"
  Write-Host ''
}

Write-Host 'Done. Refresh WeChat virtual-pay console to confirm shipped status.'
