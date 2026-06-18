# 确认 PM2 进程实际读到的虚拟支付环境变量（不是只看文件改没改）。
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\verify-pm2-virtual-pay-env.ps1

$ErrorActionPreference = 'Continue'
$Root = 'C:\zhiyuantianbao'

Write-Host '=== 1. 磁盘上的配置文件 ==='
node -e @"
const c = require('$Root/ecosystem.config.js'.replace(/\\/g,'/'));
const s = require('$Root/ecosystem.secrets.js'.replace(/\\/g,'/'));
const env = { ...(c.apps[0].env || {}), ...s };
console.log('ecosystem.config.js  WECHAT_VIRTUAL_PAY_ENV =', c.apps[0].env.WECHAT_VIRTUAL_PAY_ENV);
console.log('合并后(=PM2应加载)      WECHAT_VIRTUAL_PAY_ENV =', env.WECHAT_VIRTUAL_PAY_ENV);
console.log('合并后 prod AppKey 长度 =', (env.WECHAT_VIRTUAL_PAY_APP_KEY || '').length);
console.log('合并后 sandbox AppKey 长度 =', (env.WECHAT_VIRTUAL_PAY_SANDBOX_APP_KEY || '').length);
"@

Write-Host ''
Write-Host '=== 2. 外网 API 实际返回值（以这个为准）==='
curl.exe -s https://api.zntb.lhyun.net/api/payments/wechat/status
Write-Host ''

Write-Host ''
Write-Host '=== 3. 本地 API ==='
curl.exe -s http://127.0.0.1:8001/api/payments/wechat/status
Write-Host ''

Write-Host ''
Write-Host '判定:'
Write-Host '  - 若磁盘上是 env=1 但 API 仍是 env=0 → PM2 未加载新环境变量，见下方修复命令'
Write-Host '  - env=0 用现网 AppKey；env=1 用沙箱 AppKey，二者必须配对'
Write-Host ''
Write-Host '修复命令（改完 ecosystem.config.js / secrets.js 后执行）:'
Write-Host '  cd C:\zhiyuantianbao'
Write-Host '  pm2 delete zhiyuan-backend'
Write-Host '  pm2 start ecosystem.config.js'
Write-Host '  pm2 save'
Write-Host '  curl.exe -s https://api.zntb.lhyun.net/api/payments/wechat/status'
