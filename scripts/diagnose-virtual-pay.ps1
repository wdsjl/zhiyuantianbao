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

$secretsPath = Join-Path $Root 'ecosystem.secrets.js'
if (Test-Path $secretsPath) {
  $secretsJson = node -e "const s=require('./ecosystem.secrets.js'); process.stdout.write(JSON.stringify(s||{}));"
  if ($secretsJson) {
    ($secretsJson | ConvertFrom-Json).PSObject.Properties | ForEach-Object {
      $name = $_.Name
      $value = [string]$_.Value
      if ($value) {
        Set-Item -Path ('Env:' + $name) -Value $value
      }
    }
  }
}

Set-Location $Root
python (Join-Path $Root 'scripts\diagnose_virtual_pay.py')
