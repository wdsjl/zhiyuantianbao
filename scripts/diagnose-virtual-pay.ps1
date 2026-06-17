# Diagnose WeChat virtual-pay config (AppKey / env / access_token / pay_sig algo).
# Usage:
#   powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\diagnose-virtual-pay.ps1

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
python -c "import json; from wechat_virtual_pay_service import diagnose_virtual_pay_sig; print(json.dumps(diagnose_virtual_pay_sig(), ensure_ascii=False, indent=2))"
