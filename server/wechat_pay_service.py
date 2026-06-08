import base64
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from db import get_connection, row_to_dict
from membership_service import list_plans
from payment_service import create_pending_order, fulfill_wechat_order, get_order_by_order_no

WECHAT_PAY_HOST = 'https://api.mch.weixin.qq.com'


def get_pay_config() -> dict[str, str]:
    server_dir = Path(__file__).resolve().parent
    default_key_path = server_dir / 'certs' / 'apiclient_key.pem'
    return {
        'appid': os.getenv('WECHAT_APPID', ''),
        'mchid': os.getenv('WECHAT_MCH_ID', '1621904940'),
        'api_v3_key': os.getenv('WECHAT_PAY_API_V3_KEY', ''),
        'serial_no': os.getenv('WECHAT_PAY_SERIAL_NO', ''),
        'private_key_path': os.getenv('WECHAT_PAY_PRIVATE_KEY_PATH', str(default_key_path)),
        'notify_url': os.getenv('WECHAT_PAY_NOTIFY_URL', 'https://api.zntb.lhyun.net/api/payments/wechat/notify'),
    }


def is_wechat_pay_ready() -> bool:
    from wechat_virtual_pay_service import is_virtual_pay_ready
    return is_virtual_pay_ready()


def _load_private_key():
    config = get_pay_config()
    key_path = Path(config['private_key_path'])
    if not key_path.exists():
        raise ValueError(f'微信支付商户私钥不存在：{key_path}')
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None, backend=default_backend())


def _sign_message(message: str) -> str:
    private_key = _load_private_key()
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')


def _build_authorization(method: str, path: str, body: str) -> str:
    config = get_pay_config()
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    message = f'{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n'
    signature = _sign_message(message)
    return (
        'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{config["mchid"]}",nonce_str="{nonce}",signature="{signature}",'
        f'timestamp="{timestamp}",serial_no="{config["serial_no"]}"'
    )


def _request_wechat_pay(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = '' if payload is None else json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    request = urllib.request.Request(
        f'{WECHAT_PAY_HOST}{path}',
        data=body.encode('utf-8') if body else None,
        method=method,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': _build_authorization(method, path, body),
            'User-Agent': 'zhiyuantianbao/1.0',
        }
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise ValueError(f'微信支付接口调用失败：{detail or exc.reason}') from exc


def _amount_to_fen(amount: float) -> int:
    return int(round(float(amount) * 100))


def _get_user_openid(user_id: int) -> str:
    with get_connection() as connection:
        user = row_to_dict(connection.execute('SELECT openid FROM users WHERE user_id = ?', [user_id]).fetchone())
    openid = (user or {}).get('openid') or ''
    if not openid or openid.startswith(('dev_', 'local_', 'test_')):
        raise ValueError('请先使用微信登录后再支付')
    return openid


def _get_plan(plan_code: str) -> dict[str, Any]:
    for plan in list_plans():
        if plan.get('plan_code') == plan_code and plan.get('is_active'):
            return plan
    raise ValueError('套餐不存在或已下架')


def create_wechat_payment(
    user_id: int,
    plan_code: str,
    order_type: str = 'open',
    login_code: str | None = None,
) -> dict[str, Any]:
    from wechat_virtual_pay_service import create_virtual_payment
    return create_virtual_payment(user_id, plan_code, order_type, login_code)


def build_miniprogram_pay_params(prepay_id: str) -> dict[str, str]:
    config = get_pay_config()
    timestamp = str(int(time.time()))
    nonce_str = secrets.token_hex(16)
    package = f'prepay_id={prepay_id}'
    message = f'{config["appid"]}\n{timestamp}\n{nonce_str}\n{package}\n'
    return {
        'timeStamp': timestamp,
        'nonceStr': nonce_str,
        'package': package,
        'signType': 'RSA',
        'paySign': _sign_message(message)
    }


def query_wechat_order(order_no: str) -> dict[str, Any]:
    config = get_pay_config()
    path = f'/v3/pay/transactions/out-trade-no/{order_no}?mchid={config["mchid"]}'
    return _request_wechat_pay('GET', path)


def sync_wechat_order_status(order_no: str, user_id: int | None = None) -> dict[str, Any]:
    from wechat_virtual_pay_service import sync_virtual_order_status
    return sync_virtual_order_status(order_no, user_id)


def _decrypt_notify_resource(resource: dict[str, Any]) -> dict[str, Any]:
    api_v3_key = get_pay_config()['api_v3_key']
    if not api_v3_key:
        raise ValueError('未配置 WECHAT_PAY_API_V3_KEY')
    nonce = resource.get('nonce') or ''
    ciphertext = resource.get('ciphertext') or ''
    associated_data = resource.get('associated_data') or ''
    aesgcm = AESGCM(api_v3_key.encode('utf-8'))
    plain = aesgcm.decrypt(
        nonce.encode('utf-8'),
        base64.b64decode(ciphertext),
        associated_data.encode('utf-8')
    )
    return json.loads(plain.decode('utf-8'))


def handle_wechat_pay_notify(headers: dict[str, str], body: str) -> dict[str, str]:
    payload = json.loads(body or '{}')
    if payload.get('event_type') != 'TRANSACTION.SUCCESS':
        return {'code': 'SUCCESS', 'message': '忽略非支付成功通知'}

    resource = payload.get('resource') or {}
    if resource.get('algorithm') != 'AEAD_AES_256_GCM':
        raise ValueError('不支持的回调加密算法')

    transaction = _decrypt_notify_resource(resource)
    if transaction.get('trade_state') != 'SUCCESS':
        return {'code': 'SUCCESS', 'message': '忽略非成功交易'}

    order_no = transaction.get('out_trade_no') or ''
    transaction_id = transaction.get('transaction_id') or ''
    if not order_no:
        raise ValueError('回调缺少订单号')

    fulfill_wechat_order(order_no, transaction_id, body)
    return {'code': 'SUCCESS', 'message': '成功'}
