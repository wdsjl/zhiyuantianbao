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

# 套餐虚拟道具配置：goodsPrice 为分
PLAN_VIRTUAL_PRODUCTS: dict[str, dict[str, Any]] = {
    'trial': {'product_id': 'trial', 'goods_price_fen': 1990},
    'premium': {'product_id': 'premium', 'goods_price_fen': 29800},
}

PAID_ORDER_STATUSES = {2, 3, 4}


def _clean_secret(value: str | None) -> str:
    return (value or '').strip().strip('"').strip("'")


def get_virtual_pay_config() -> dict[str, Any]:
    env = int(str(os.getenv('WECHAT_VIRTUAL_PAY_ENV', '0') or '0').strip() or '0')
    prod_key = _clean_secret(os.getenv('WECHAT_VIRTUAL_PAY_APP_KEY', ''))
    sandbox_key = _clean_secret(os.getenv('WECHAT_VIRTUAL_PAY_SANDBOX_APP_KEY', ''))
    return {
        'offer_id': (os.getenv('WECHAT_VIRTUAL_PAY_OFFER_ID', '1450554502') or '1450554502').strip(),
        'env': 1 if env == 1 else 0,
        'app_key': sandbox_key if env == 1 else prod_key,
        'prod_app_key': prod_key,
        'sandbox_app_key': sandbox_key,
        'appid': (os.getenv('WECHAT_APPID', '') or '').strip(),
        'secret': (os.getenv('WECHAT_SECRET', '') or '').strip(),
    }


def is_virtual_pay_ready() -> bool:
    return not get_virtual_pay_status()['missing']


def get_virtual_pay_status() -> dict[str, Any]:
    config = get_virtual_pay_config()
    missing: list[str] = []
    if not config['appid']:
        missing.append('WECHAT_APPID')
    if not config['secret']:
        missing.append('WECHAT_SECRET')
    if not config['offer_id']:
        missing.append('WECHAT_VIRTUAL_PAY_OFFER_ID')
    if not config['app_key']:
        key_name = 'WECHAT_VIRTUAL_PAY_SANDBOX_APP_KEY' if config['env'] == 1 else 'WECHAT_VIRTUAL_PAY_APP_KEY'
        missing.append(key_name)
    return {
        'enabled': not missing,
        'mode': 'virtual_pay',
        'env': config['env'],
        'offer_id': config['offer_id'],
        'appid_configured': bool(config['appid']),
        'secret_configured': bool(config['secret']),
        'app_key_configured': bool(config['app_key']),
        'missing': missing,
        'hint': (
            '虚拟支付无需商户证书 apiclient_key.pem；请在 ecosystem.secrets.js 配置 WECHAT_SECRET 与 WECHAT_VIRTUAL_PAY_APP_KEY 后执行 pm2 restart zhiyuan-backend --update-env'
            if missing else '虚拟支付已就绪'
        ),
    }


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
    env_product_id = _clean_secret(os.getenv(f'WECHAT_VIRTUAL_PRODUCT_{plan_code.upper()}', ''))
    env_goods_price = _clean_secret(os.getenv(f'WECHAT_VIRTUAL_GOODS_PRICE_{plan_code.upper()}', ''))
    product_id = env_product_id or defaults.get('product_id') or plan_code
    if env_goods_price:
        goods_price_fen = int(env_goods_price)
    else:
        goods_price_fen = int(round(price * 100))
    return {
        'plan': plan,
        'product_id': product_id,
        'goods_price_fen': goods_price_fen,
    }


def _calc_pay_sig(uri: str, sign_data: str, app_key: str) -> str:
    message = f'{uri}&{sign_data}'
    return hmac.new(app_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()


def _calc_user_signature(sign_data: str, session_key: str) -> str:
    return hmac.new(session_key.encode('utf-8'), sign_data.encode('utf-8'), hashlib.sha256).hexdigest()


def _compact_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def _parse_remote_order_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        if isinstance(payload.get('order'), dict):
            return payload['order']
        return payload
    text = str(payload or '').strip()
    if not text:
        return {}
    if text.startswith('{'):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return _parse_remote_order_payload(parsed)
    return {}


def _split_virtual_pay_ids(remote_order: dict[str, Any]) -> tuple[str, str]:
    """返回 (微信虚拟支付内部单号 VPO..., 微信支付交易单号)。"""
    virtual_id = str(remote_order.get('wx_order_id') or '').strip()
    txn_id = str(remote_order.get('wxpay_order_id') or remote_order.get('TransactionId') or '').strip()
    return virtual_id, txn_id


def _resolve_virtual_pay_ids(order: dict[str, Any], remote_order: dict[str, Any] | None = None) -> tuple[str, str]:
    remote = remote_order or _parse_remote_order_payload(order.get('wx_notify_raw'))
    virtual_id, txn_id = _split_virtual_pay_ids(remote)
    if not txn_id:
        txn_id = str(order.get('wx_transaction_id') or '').strip()
    return virtual_id, txn_id


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


def _is_pay_sig_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return 'pay_sig' in text or '签名' in text or '268490003' in text


def _xpay_env_candidates() -> list[dict[str, Any]]:
    config = get_virtual_pay_config()
    candidates = [config]
    for env, app_key in ((0, config['prod_app_key']), (1, config['sandbox_app_key'])):
        if not app_key:
            continue
        if env == config['env'] and app_key == config['app_key']:
            continue
        candidates.append({**config, 'env': env, 'app_key': app_key})
    return candidates


def _request_xpay_api_once(path: str, post_body: str, app_key: str) -> dict[str, Any]:
    pay_sig = _calc_pay_sig(path, post_body, app_key)
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


def _request_xpay_api(path: str, body: dict[str, Any]) -> dict[str, Any]:
    last_error: ValueError | None = None
    seen: set[tuple[int, str]] = set()
    for candidate in _xpay_env_candidates():
        trial_body = dict(body)
        if 'env' in trial_body:
            trial_body['env'] = candidate['env']
        post_body = _compact_json(trial_body)
        key_sig = (candidate['env'], candidate['app_key'])
        if key_sig in seen:
            continue
        seen.add(key_sig)
        try:
            return _request_xpay_api_once(path, post_body, candidate['app_key'])
        except ValueError as exc:
            if _is_pay_sig_error(exc):
                last_error = exc
                continue
            raise
    if last_error:
        raise ValueError(
            f'{last_error}（已尝试现网/沙箱 AppKey，请核对 ecosystem.secrets.js 中 '
            f'WECHAT_VIRTUAL_PAY_APP_KEY、WECHAT_VIRTUAL_PAY_SANDBOX_APP_KEY 与 '
            f'WECHAT_VIRTUAL_PAY_ENV 是否与微信后台「虚拟支付-基础配置」一致）'
        ) from last_error
    raise ValueError('虚拟支付接口调用失败')


def diagnose_virtual_pay_sig() -> dict[str, Any]:
    """诊断虚拟支付配置与 pay_sig 算法，便于排查补发货失败。"""
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
    except ValueError as exc:
        token_error = str(exc)

    def _mask_key(key: str) -> str:
        key = key or ''
        if len(key) <= 4:
            return '****' if key else ''
        return f'{key[:2]}...{key[-4:]}'

    return {
        **status,
        'algo_ok': algo_ok,
        'access_token_ok': token_ok,
        'access_token_error': token_error,
        'app_key_mask': _mask_key(config['app_key']),
        'prod_app_key_mask': _mask_key(config['prod_app_key']),
        'sandbox_app_key_mask': _mask_key(config['sandbox_app_key']),
        'hint': (
            'pay_sig 算法正常，access_token 正常。若补发货仍失败，请确认微信后台「现网 AppKey」'
            '与 WECHAT_VIRTUAL_PAY_APP_KEY 完全一致（env=0 用现网，env=1 用沙箱）。'
            if algo_ok and token_ok and status.get('enabled') else status.get('hint', '')
        ),
    }


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

    # attach 使用简单字符串，避免嵌套 JSON 在部分客户端引发签名校验问题
    attach = f'{plan_code}:{user_id}:{order_type}'
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


def notify_provide_goods(order_no: str, wx_order_id: str = '') -> dict[str, Any]:
    """通知微信虚拟支付：已发货完成（用于回调失败时手动补发）。"""
    config = get_virtual_pay_config()
    body: dict[str, Any] = {'env': config['env']}
    notify_id = str(wx_order_id or '').strip()
    if notify_id.startswith('VPO'):
        body['wx_order_id'] = notify_id
    elif notify_id:
        body['order_id'] = order_no
    else:
        body['order_id'] = order_no
    return _request_xpay_api('/xpay/notify_provide_goods', body)


def repair_virtual_order(
    order_no: str,
    user_id: int | None = None,
    *,
    assume_paid: bool = False,
) -> dict[str, Any]:
    """查询微信订单 → 本地开通会员 → 通知微信已发货。

    assume_paid=True 时跳过查单，适用于微信后台已显示支付成功但 pay_sig 查单失败的情况。
    查单因 pay_sig 失败时也会自动跳过查单并继续本地开通 + 通知发货。
    """
    order = get_order_by_order_no(order_no)
    if not order:
        raise ValueError('订单不存在')
    if user_id is not None and int(order['user_id']) != int(user_id):
        raise ValueError('无权操作该订单')
    if str(order.get('pay_method') or '') != 'virtual_pay':
        raise ValueError('仅虚拟支付订单支持补发货')

    if not is_virtual_pay_ready():
        raise ValueError('虚拟支付未配置完成')

    wx_virtual_order_id = ''
    wxpay_transaction_id = ''
    remote_raw = ''
    query_skipped = assume_paid

    if not assume_paid:
        try:
            remote = query_virtual_order(order_no)
        except ValueError as exc:
            if _is_pay_sig_error(exc):
                query_skipped = True
            else:
                raise
        else:
            remote_order = remote.get('order') or {}
            status = int(remote_order.get('status') or 0)
            if status not in PAID_ORDER_STATUSES:
                raise ValueError('微信侧订单尚未支付成功，无法发货')
            wx_virtual_order_id, wxpay_transaction_id = _split_virtual_pay_ids(remote_order)
            remote_raw = _compact_json(remote_order)

    if not wx_virtual_order_id and not wxpay_transaction_id:
        wx_virtual_order_id, wxpay_transaction_id = _resolve_virtual_pay_ids(order)

    fulfilled = False
    if order.get('pay_status') != 'paid':
        notify_raw = remote_raw or ('manual_repair_assume_paid' if query_skipped else '')
        fulfill_wechat_order(
            order_no,
            wxpay_transaction_id or wx_virtual_order_id,
            notify_raw,
            pay_method='virtual_pay',
        )
        fulfilled = True

    try:
        notify_provide_goods(order_no, wx_virtual_order_id)
    except ValueError as exc:
        order = get_order_by_order_no(order_no)
        if fulfilled or order.get('pay_status') == 'paid':
            raise ValueError(
                f'本地会员已开通，但通知微信发货失败：{exc}。'
                f'可尝试 repair_virtual_order(..., assume_paid=True)，'
                f'或核对 WECHAT_VIRTUAL_PAY_ENV 与订单支付环境是否一致'
            ) from exc
        raise

    order = get_order_by_order_no(order_no)
    message = '已同步开通会员并通知微信发货完成'
    if query_skipped:
        message += '（已跳过查单，按微信后台已支付处理）'
    return {
        'order': order,
        'fulfilled': fulfilled,
        'notified': True,
        'query_skipped': query_skipped,
        'message': message,
    }


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
        wx_virtual_order_id, wxpay_transaction_id = _split_virtual_pay_ids(remote_order)
        fulfill_wechat_order(
            order_no,
            wxpay_transaction_id or wx_virtual_order_id,
            _compact_json(remote_order),
            pay_method='virtual_pay',
        )
        try:
            notify_provide_goods(order_no, wx_virtual_order_id)
        except ValueError:
            pass
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
