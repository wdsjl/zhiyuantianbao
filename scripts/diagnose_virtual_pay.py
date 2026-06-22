"""虚拟支付配置诊断（不依赖 wechat_virtual_pay_service.diagnose_virtual_pay_sig）。"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

from membership_service import list_plans  # noqa: E402
from wechat_virtual_pay_service import (  # noqa: E402
    _calc_pay_sig,
    _get_access_token,
    get_virtual_pay_config,
    get_virtual_pay_status,
    PLAN_VIRTUAL_PRODUCTS,
)


def mask_key(key: str) -> str:
    key = key or ''
    if len(key) <= 4:
        return '****' if key else ''
    return f'{key[:2]}...{key[-4:]}'


def main() -> None:
    status = get_virtual_pay_status()
    config = get_virtual_pay_config()

    uri = '/xpay/query_user_balance'
    appkey = '12345'
    post_body = '{"openid": "xxx", "user_ip": "127.0.0.1", "env": 0}'
    expected = 'c37809f27c6d7fd1837ad2500a04512b66b34fd793a39a385fade56dca89a4b5'
    algo_ok = _calc_pay_sig(uri, post_body, appkey) == expected

    token_ok = False
    token_error = ''
    try:
        _get_access_token()
        token_ok = True
    except Exception as exc:  # noqa: BLE001
        token_error = str(exc)

    plans = []
    for item in list_plans():
        code = item.get('plan_code')
        if code not in ('trial', 'premium'):
            continue
        price = float(item.get('price') or 0)
        defaults = PLAN_VIRTUAL_PRODUCTS.get(code, {})
        plans.append({
            'plan_code': code,
            'plan_name': item.get('plan_name'),
            'db_price_yuan': price,
            'sign_goods_price_fen': int(round(price * 100)),
            'default_product_id': defaults.get('product_id') or code,
            'catalog_goods_price_fen': defaults.get('goods_price_fen'),
        })

    result = {
        **status,
        'algo_ok': algo_ok,
        'access_token_ok': token_ok,
        'access_token_error': token_error,
        'app_key_mask': mask_key(config.get('app_key')),
        'prod_app_key_mask': mask_key(config.get('prod_app_key') or config.get('app_key')),
        'sandbox_app_key_mask': mask_key(config.get('sandbox_app_key', '')),
        'plans': plans,
        'hint': (
            'pay_sig 算法与 access_token 正常。若小程序仍 PAY_SIG_INVALID：'
            '1) 核对微信后台 AppKey 与 ecosystem.secrets.js；'
            '2) 核对道具 productId/价格(分)与 sign_goods_price_fen 一致；'
            '3) 体验版可试 WECHAT_VIRTUAL_PAY_ENV=1 + 沙箱 AppKey。'
            if algo_ok and token_ok and status.get('enabled') else status.get('hint', '')
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
