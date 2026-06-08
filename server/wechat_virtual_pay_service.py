import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from auth_service import get_wechat_session
from db import get_connection, row_to_dict
from membership_service import list_plans
from payment_service import create_pending_order, fulfill_wechat_order, get_order_by_order_no

WECHAT_API_HOST = 'https://api.weixin.qq.com'

# 套餐虚拟道具配置：goodsPrice 为分；星鼎豆 = 金额(元) × 10
PLAN_VIRTUAL_PRODUCTS: dict[str, dict[str, Any]] = {
    'trial': {'product_id': 'trial', 'goods_price_fen': 1990, 'bean_price': 199},
    'standard': {'product_id': 'standard', 'goods_price_fen': 9900, 'bean_price': 990},
    'premium': {'product_id': 'premium', 'goods_price_fen': 16800, 'bean_price': 1680},
}

PAID_ORDER_STATUSES = {2, 3, 4}


def get_virtual_pay_config() -> dict[str, Any]:
    env = int(os.getenv('WECHAT_VIRTUAL_PAY_ENV', '0') or '0')
    return {
        'offer_id': os.getenv('WECHAT_VIRTUAL_PAY_OFFER_ID', '1450554502'),
        'env': 1 if env == 1 else 0,
        'app_key': (
            os.getenv('WECHAT_VIRTUAL_PAY_SANDBOX_APP_KEY', '')
            if env == 1
            else os.getenv('WECHAT_VIRTUAL_PAY_APP_KEY', '')
        ),
        'appid': os.getenv('WECHAT_APPID', ''),
        'secret': os.getenv('WECHAT_SECRET', ''),
    }


def is_virtual_pay_ready() -> bool:
    config = get_virtual_pay_config()
    return bool(config['offer_id'] and config['app_key'] and config['appid'] and config['secret'])


def _get_plan_product(plan_code: str) -> dict[str, Any]:
    plan = None
    for item in list_plans():
        if item.get('plan_code') == plan_code and item.get('is_active'):
            plan = item
            break
    if not plan:
        raise ValueError('套餐不存在或已下架')

    price = float(plan.get('price') or 0)
    if price <= 0:
        raise ValueError('免费套餐无需支付')

    defaults = PLAN_VIRTUAL_PRODUCTS.get(plan_code, {})
    env_product_id = os.getenv(f'WECHAT_VIRTUAL_PRODUCT_{plan_code.upper()}', '').strip()
    product_id = env_product_id or defaults.get('product_id') or plan_code
    goods_price_fen = int(round(price * 100))
    bean_price = int(round(price * 10))
    return {
        'plan': plan,
        'product_id': product_id,
        'goods_price_fen': goods_price_fen,
        'bean_price': bean_price,
    }


def _calc_pay_sig(uri: str, sign_data: str, app_key: str) -> str:
    message = f'{uri}&{sign_data}'
    return hmac.new(app_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()


def _calc_user_signature(sign_data: str, session_key: str) -> str:
    return hmac.new(session_key.encode('utf-8'), sign_data.encode('utf-8'), hashlib.sha256).hexdigest()


def _compact_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def _get_user_openid(user_id: int) -> str:
    with get_connection() as connection:
        user = row_to_dict(connection.execute('SELECT openid FROM users WHERE user_id = ?', [user_id]).fetchone())
    openid = (user or {}).get('openid') or ''
    if not openid or openid.startswith(('dev_', 'local_', 'test_')):
        raise ValueError('请先使用微信登录后再支付')
    return openid


def _get_access_token() -> str:
    config = get_virtual_pay_config()
    if not config['appid'] or not config['secret']:
        raise ValueError('未配置 WECHAT_APPID / WECHAT_SECRET')
    query = urllib.parse.urlencode({
        'grant_type': 'client_credential',
        'appid': config['appid'],
        'secret': config['secret'],
    })
    with urllib.request.urlopen(f'{WECHAT_API_HOST}/cgi-bin/token?{query}', timeout=8) as response:
        data = json.loads(response.read().decode('utf-8'))
    if data.get('errcode'):
        raise ValueError(data.get('errmsg', '获取 access_token 失败'))
    token = data.get('access_token') or ''
    if not token:
        raise ValueError('获取 access_token 失败')
    return token


def _request_xpay_api(path: str, body: dict[str, Any]) -> dict[str, Any]:
    config = get_virtual_pay_config()
    post_body = _compact_json(body)
    pay_sig = _calc_pay_sig(path, post_body, config['app_key'])
    access_token = _get_access_token()
    query = urllib.parse.urlencode({'access_token': access_token, 'pay_sig': pay_sig})
    request = urllib.request.Request(
        f'{WECHAT_API_HOST}{path}?{query}',
        data=post_body.encode('utf-8'),
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode('utf-8'))
    if data.get('errcode') not in (0, None):
        raise ValueError(data.get('errmsg') or f'虚拟支付接口调用失败：{data.get("errcode")}')
    return data


def create_virtual_payment(user_id: int, plan_code: str, order_type: str = 'open', login_code: str | None = None) -> dict[str, Any]:
    if not is_virtual_pay_ready():
        raise ValueError('虚拟支付尚未配置完成，请联系管理员检查 OfferID 与 AppKey')

    if not login_code:
        raise ValueError('支付前请先调用 wx.login 获取 code')

    session = get_wechat_session(login_code.strip())
    if not session or not session.get('session_key'):
        raise ValueError('微信登录态失效，请重新进入小程序后再支付')

    product = _get_plan_product(plan_code)
    plan = product['plan']
    openid = _get_user_openid(user_id)
    config = get_virtual_pay_config()

    order_no, order_id = create_pending_order(
        user_id=user_id,
        plan_code=plan_code,
        amount=float(plan.get('price') or 0),
        order_type=order_type,
        pay_method='virtual_pay',
    )

    attach = _compact_json({
        'user_id': user_id,
        'plan_code': plan_code,
        'order_type': order_type,
    })
    sign_data_obj = {
        'offerId': config['offer_id'],
        'buyQuantity': 1,
        'env': config['env'],
        'currencyType': 'CNY',
        'productId': product['product_id'],
        'goodsPrice': product['goods_price_fen'],
        'outTradeNo': order_no,
        'attach': attach,
    }
    sign_data = _compact_json(sign_data_obj)
    pay_sig = _calc_pay_sig('requestVirtualPayment', sign_data, config['app_key'])
    signature = _calc_user_signature(sign_data, session['session_key'])

    return {
        'order_id': order_id,
        'order_no': order_no,
        'plan_code': plan_code,
        'plan_name': plan.get('plan_name'),
        'amount': float(plan.get('price') or 0),
        'bean_price': product['bean_price'],
        'mode': 'short_series_goods',
        'virtual_pay': {
            'signData': sign_data,
            'paySig': pay_sig,
            'signature': signature,
        },
    }


def query_virtual_order(order_no: str, openid: str | None = None) -> dict[str, Any]:
    config = get_virtual_pay_config()
    if not openid:
        order = get_order_by_order_no(order_no)
        if not order:
            raise ValueError('订单不存在')
        openid = _get_user_openid(int(order['user_id']))
    return _request_xpay_api('/xpay/query_order', {
        'openid': openid,
        'env': config['env'],
        'order_id': order_no,
    })


def sync_virtual_order_status(order_no: str, user_id: int | None = None) -> dict[str, Any]:
    order = get_order_by_order_no(order_no)
    if not order:
        raise ValueError('订单不存在')
    if user_id is not None and int(order['user_id']) != int(user_id):
        raise ValueError('无权查看该订单')
    if order.get('pay_status') == 'paid':
        return {'order': order, 'synced': False}

    if not is_virtual_pay_ready():
        return {'order': order, 'synced': False}

    try:
        remote = query_virtual_order(order_no)
    except ValueError:
        return {'order': order, 'synced': False}

    remote_order = remote.get('order') or {}
    status = int(remote_order.get('status') or 0)
    if status in PAID_ORDER_STATUSES:
        transaction_id = remote_order.get('wxpay_order_id') or remote_order.get('wx_order_id') or ''
        fulfill_wechat_order(order_no, transaction_id, _compact_json(remote_order), pay_method='virtual_pay')
        order = get_order_by_order_no(order_no)
        return {'order': order, 'synced': True}
    return {'order': order, 'synced': False}


def _xml_text(root: ET.Element, tag: str) -> str:
    node = root.find(tag)
    return (node.text or '').strip() if node is not None else ''


def _parse_notify_payload(body: str) -> dict[str, str]:
    text = (body or '').strip()
    if not text:
        return {}
    if text.startswith('{'):
        data = json.loads(text)
        return {str(key): str(value or '') for key, value in data.items()}
    root = ET.fromstring(text)
    return {child.tag: (child.text or '').strip() for child in root}


def handle_virtual_deliver_notify(body: str) -> dict[str, Any]:
    payload = _parse_notify_payload(body)
    event = payload.get('Event') or payload.get('event') or ''
    if event and event != 'xpay_goods_deliver_notify':
        return {'ErrCode': 0, 'ErrMsg': 'success'}

    order_no = payload.get('OutTradeNo') or payload.get('out_trade_no') or ''
    if not order_no:
        raise ValueError('发货通知缺少订单号')

    transaction_id = ''
    wechat_pay_info = payload.get('WeChatPayInfo')
    if isinstance(wechat_pay_info, dict):
        transaction_id = wechat_pay_info.get('TransactionId') or ''
    fulfill_wechat_order(order_no, transaction_id, body, pay_method='virtual_pay')
    return {'ErrCode': 0, 'ErrMsg': 'success'}


def make_refund_no(order_id: int) -> str:
    return f'R{time.strftime("%Y%m%d%H%M%S")}{order_id}'


def create_virtual_refund(order: dict[str, Any], reason: str = '') -> dict[str, Any]:
    if not is_virtual_pay_ready():
        raise ValueError('虚拟支付未配置完成，无法原路退款')

    order_no = str(order.get('order_no') or '').strip()
    if not order_no:
        raise ValueError('订单号缺失，无法发起退款')

    openid = _get_user_openid(int(order['user_id']))
    config = get_virtual_pay_config()
    remote = query_virtual_order(order_no, openid)
    remote_order = remote.get('order') or {}
    left_fee = int(remote_order.get('left_fee') or 0)
    if left_fee <= 0:
        left_fee = int(round(float(order.get('amount') or 0) * 100))
    if left_fee <= 0:
        raise ValueError('订单可退金额无效，无法退款')

    refund_order_id = make_refund_no(int(order.get('order_id') or 0))
    refund_note = (reason or '管理员退款')[:1024]
    result = _request_xpay_api('/xpay/refund_order', {
        'openid': openid,
        'order_id': order_no,
        'refund_order_id': refund_order_id,
        'left_fee': left_fee,
        'refund_fee': left_fee,
        'biz_meta': refund_note,
        'refund_reason': '5',
        'req_from': '1',
        'env': config['env'],
    })
    return {
        'refund_id': result.get('refund_wx_order_id') or '',
        'out_refund_no': result.get('refund_order_id') or refund_order_id,
        'raw': result,
    }
