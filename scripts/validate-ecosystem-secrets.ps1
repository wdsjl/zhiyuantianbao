# 部署前校验 ecosystem.secrets.js 语法与必填项（防止支付再次因配置文件损坏而挂掉）
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\validate-ecosystem-secrets.ps1

$ErrorActionPreference = 'Stop'
$Root = 'C:\zhiyuantianbao'
$SecretsPath = Join-Path $Root 'ecosystem.secrets.js'

if (-not (Test-Path $SecretsPath)) {
  throw "缺少 $SecretsPath — 请从 ecosystem.secrets.example.js 复制并填写"
}

Set-Location $Root
$checkJson = node -e @"
const path = require('path');
const secretsPath = path.join(process.cwd(), 'ecosystem.secrets.js');
let secrets;
try {
  secrets = require(secretsPath);
} catch (error) {
  console.error('SYNTAX_ERROR:', error.message);
  process.exit(2);
}
const required = ['WECHAT_SECRET', 'WECHAT_VIRTUAL_PAY_APP_KEY'];
const missing = required.filter((key) => !String(secrets[key] || '').trim());
const dupKeys = (require('fs').readFileSync(secretsPath, 'utf8').match(/WECHAT_VIRTUAL_PAY_APP_KEY/g) || []).length;
const result = {
  ok: missing.length === 0 && dupKeys === 1,
  secret: !!secrets.WECHAT_SECRET,
  appKey: !!secrets.WECHAT_VIRTUAL_PAY_APP_KEY,
  missing,
  duplicateAppKeyLines: dupKeys
};
console.log(JSON.stringify(result));
if (!result.ok) process.exit(1);
"@

if ($LASTEXITCODE -eq 2) {
  throw 'ecosystem.secrets.js 语法错误（常见：上一行缺逗号、AppKey 重复两行）'
}
if ($LASTEXITCODE -ne 0) {
  throw "ecosystem.secrets.js 校验失败: $checkJson"
}

Write-Host "ecosystem.secrets.js OK: $checkJson"

$configJson = node -e "const c=require('./ecosystem.config.js'); const e=c.apps[0].env||{}; console.log(JSON.stringify({env:e.WECHAT_VIRTUAL_PAY_ENV, trial:e.WECHAT_VIRTUAL_PRODUCT_TRIAL, premium:e.WECHAT_VIRTUAL_PRODUCT_PREMIUM, premiumFen:e.WECHAT_VIRTUAL_GOODS_PRICE_PREMIUM}));"
Write-Host "ecosystem.config.js payment env: $configJson"

if ($configJson -notmatch 'xdptk' -or $configJson -notmatch 'xdbjk' -or $configJson -notmatch '29800') {
  throw 'ecosystem.config.js 虚拟支付道具配置异常'
}

Write-Host 'VALIDATE SECRETS PASSED'
