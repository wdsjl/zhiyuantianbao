# 仅热修虚拟支付 500：不替换整份 main.py，避免缺模块导致 502。
# 用法: powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\sync-payment-hotfix-only.ps1

$ErrorActionPreference = 'Stop'
$Branch = 'cursor/fix-payment-500-0c75'
$Base = 'https://raw.githubusercontent.com/wdsjl/zhiyuantianbao/' + $Branch
$Root = 'C:\zhiyuantianbao'
$ServerDir = Join-Path $Root 'server'

New-Item -ItemType Directory -Path $ServerDir -Force | Out-Null

foreach ($name in @('payment_service.py', 'auth_service.py')) {
  $dest = Join-Path $ServerDir $name
  if (Test-Path $dest) {
    Copy-Item $dest ($dest + '.bak') -Force
  }
  $url = $Base + '/server/' + $name
  Write-Host ('Downloading ' + $name + ' ...')
  curl.exe -fsSL -o $dest $url
  if (-not (Test-Path $dest)) { throw ('Download failed: ' + $name) }
}

$patchScript = Join-Path $ServerDir 'patch_payment_endpoint.py'
@'
from pathlib import Path

MAIN = Path(__file__).resolve().parent / 'main.py'
text = MAIN.read_text(encoding='utf-8')

OLD = """@app.post('/api/payments/wechat/create')
def api_wechat_pay_create(payload: PaymentCreateRequest):
    try:
        return create_wechat_payment(
            payload.user_id,
            payload.plan_code,
            payload.request_type,
            payload.login_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc"""

NEW = """@app.post('/api/payments/wechat/create')
def api_wechat_pay_create(payload: PaymentCreateRequest):
    import logging
    import sqlite3

    logger = logging.getLogger('zhiyuan.payment')
    try:
        return create_wechat_payment(
            payload.user_id,
            payload.plan_code,
            payload.request_type,
            payload.login_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        logger.exception('payment create db error user_id=%s plan=%s', payload.user_id, payload.plan_code)
        raise HTTPException(status_code=400, detail='创建支付订单失败，请稍后重试') from exc
    except Exception as exc:
        logger.exception('payment create failed user_id=%s plan=%s', payload.user_id, payload.plan_code)
        raise HTTPException(status_code=500, detail='支付服务异常，请稍后重试') from exc"""

if 'zhiyuan.payment' in text:
    print('main.py payment endpoint already patched')
elif OLD in text:
    MAIN.write_text(text.replace(OLD, NEW), encoding='utf-8')
    print('main.py payment endpoint patched OK')
else:
    raise SystemExit('main.py 中未找到支付接口旧代码，请手动对照 PR #54 修改 api_wechat_pay_create')
'@ | Set-Content -Path $patchScript -Encoding UTF8

Write-Host ''
Write-Host 'Patching main.py (payment endpoint only)...'
Set-Location $ServerDir
python $patchScript
if ($LASTEXITCODE -ne 0) { throw 'patch_payment_endpoint.py failed' }

Write-Host ''
Write-Host '=== import test ==='
python -c "import main; print('import main: OK')"
if ($LASTEXITCODE -ne 0) { throw 'import main failed - see traceback above' }

Write-Host ''
Write-Host 'Restarting pm2...'
Set-Location $Root
pm2 restart zhiyuan-backend --update-env
Start-Sleep -Seconds 2
curl.exe -s http://127.0.0.1:8001/health
Write-Host ''
curl.exe -s https://api.zntb.lhyun.net/health
Write-Host ''
