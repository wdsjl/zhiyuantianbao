"""抖音团购/抖店三方券：发券 SPI + 微信会员中心兑券开会员。"""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from membership_service import grant_membership, list_plans
from payment_service import create_pending_order, get_order_by_order_no

COUPON_CODE_PATTERN = re.compile(r'^[A-Z0-9]{10,24}$')

# third_sku_id 默认与系统 plan_code 一致，可在抖音商品侧按此填写
DEFAULT_THIRD_SKU_PLAN = {
    'trial': 'trial',
    'standard': 'standard',
    'premium': 'premium',
}

SKU_NAME_HINTS = (
    ('普通', 'trial'),
    ('黄金', 'standard'),
    ('金卡', 'standard'),
    ('白金', 'premium'),
)


def ensure_douyin_coupon_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS douyin_coupons (
              coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
              coupon_code TEXT NOT NULL UNIQUE,
              douyin_order_id TEXT NOT NULL,
              plan_code TEXT NOT NULL,
              sku_id TEXT,
              third_sku_id TEXT,
              sku_name TEXT,
              copies INTEGER NOT NULL DEFAULT 1,
              status TEXT NOT NULL DEFAULT 'issued'
                CHECK(status IN ('issued', 'redeemed', 'cancelled')),
              user_id INTEGER,
              payment_order_no TEXT,
              redeem_channel TEXT NOT NULL DEFAULT 'wechat_membership',
              issued_payload TEXT,
              redeemed_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(douyin_order_id, coupon_code)
            )
            '''
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_douyin_coupons_order ON douyin_coupons(douyin_order_id)'
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_douyin_coupons_status ON douyin_coupons(status, created_at)'
        )
        connection.commit()


def _normalize_coupon_code(code: str) -> str:
    value = (code or '').strip().upper().replace('-', '').replace(' ', '')
    if not value:
        raise ValueError('请输入兑换码')
    if not COUPON_CODE_PATTERN.match(value):
        raise ValueError('兑换码格式不正确，请核对抖音订单中的券码')
    return value


def _generate_coupon_code(douyin_order_id: str, index: int = 0) -> str:
    seed = f'{douyin_order_id}:{index}:{time.time()}:{secrets.token_hex(4)}'
    digest = hashlib.sha1(seed.encode('utf-8')).hexdigest().upper()
    return f'ZD{digest[:10]}'


def resolve_plan_code(sku: dict[str, Any] | None, third_sku_id: str = '', sku_id: str = '') -> str:
    import os

    third_sku_id = (third_sku_id or (sku or {}).get('third_sku_id') or '').strip()
    sku_id = (sku_id or (sku or {}).get('sku_id') or '').strip()
    sku_name = (sku or {}).get('sku_name') or ''

    if third_sku_id:
        for plan in list_plans():
            if plan.get('plan_code') == third_sku_id and plan.get('is_active'):
                return third_sku_id
        env_plan = os.getenv(f'DOUYIN_THIRD_SKU_{third_sku_id.upper()}', '').strip()
        if env_plan:
            return env_plan

    for env_key, plan_code in (
        ('DOUYIN_SKU_ID_TRIAL', 'trial'),
        ('DOUYIN_SKU_ID_STANDARD', 'standard'),
        ('DOUYIN_SKU_ID_PREMIUM', 'premium'),
    ):
        if sku_id and sku_id == (os.getenv(env_key) or '').strip():
            return plan_code

    for hint, plan_code in SKU_NAME_HINTS:
        if hint in sku_name:
            return plan_code

    if third_sku_id in DEFAULT_THIRD_SKU_PLAN:
        return third_sku_id

    raise ValueError(f'无法识别抖音商品对应的会员套餐，请配置 third_sku_id 或 SKU 映射：{sku_name or sku_id or third_sku_id}')


def issue_coupons_from_spi(payload: dict[str, Any]) -> dict[str, Any]:
    douyin_order_id = str(payload.get('order_id') or '').strip()
    if not douyin_order_id:
        raise ValueError('缺少抖音订单号 order_id')

    sku = payload.get('sku') if isinstance(payload.get('sku'), dict) else {}
    plan_code = resolve_plan_code(
        sku,
        str(payload.get('third_sku_id') or ''),
        str(payload.get('sku_id') or ''),
    )
    copies = int(payload.get('copies') or 1)
    if copies <= 0:
        copies = 1
    if copies > 20:
        raise ValueError('单次发券份数过多')

    plan = next((item for item in list_plans() if item.get('plan_code') == plan_code), None)
    if not plan or not plan.get('is_active'):
        raise ValueError('会员套餐不存在或已下架')

    sku_id = str((sku or {}).get('sku_id') or payload.get('sku_id') or '')
    third_sku_id = str((sku or {}).get('third_sku_id') or payload.get('third_sku_id') or plan_code)
    sku_name = str((sku or {}).get('sku_name') or '')

    issued_codes: list[str] = []
    vouchers: list[dict[str, Any]] = []

    with get_connection() as connection:
        existing = rows_to_dicts(
            connection.execute(
                '''
                SELECT coupon_code FROM douyin_coupons
                WHERE douyin_order_id = ? AND status = 'issued'
                ORDER BY coupon_id ASC
                ''',
                [douyin_order_id],
            ).fetchall()
        )
        if existing:
            issued_codes = [row['coupon_code'] for row in existing]
        else:
            for index in range(copies):
                coupon_code = _generate_coupon_code(douyin_order_id, index)
                connection.execute(
                    '''
                    INSERT INTO douyin_coupons (
                      coupon_code, douyin_order_id, plan_code, sku_id, third_sku_id, sku_name,
                      copies, status, issued_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'issued', ?)
                    ''',
                    [
                        coupon_code,
                        douyin_order_id,
                        plan_code,
                        sku_id,
                        third_sku_id,
                        sku_name,
                        copies,
                        str(payload),
                    ],
                )
                issued_codes.append(coupon_code)
            connection.commit()

    for index, coupon_code in enumerate(issued_codes):
        project_id = str(index + 1)
        vouchers.append({
            'entrance': {
                'project_id': project_id,
                'certificate_nos': [coupon_code],
                'urls': [
                    'https://api.zntb.lhyun.net/api/douyin/redeem-hint?code=' + coupon_code,
                ],
            },
        })

    return {
        'data': {
            'error_code': 0,
            'description': 'success',
            'result': 1,
            'vouchers': vouchers,
        }
    }


def redeem_coupon(user_id: int, coupon_code: str) -> dict[str, Any]:
    code = _normalize_coupon_code(coupon_code)
    ensure_douyin_coupon_tables()

    with get_connection() as connection:
        coupon = row_to_dict(
            connection.execute(
                'SELECT * FROM douyin_coupons WHERE coupon_code = ?',
                [code],
            ).fetchone()
        )
        if not coupon:
            raise ValueError('兑换码不存在，请检查是否输入正确')
        if coupon.get('status') == 'redeemed':
            if coupon.get('user_id') and int(coupon['user_id']) == int(user_id):
                order = None
                if coupon.get('payment_order_no'):
                    order = get_order_by_order_no(coupon['payment_order_no'])
                return {
                    'already_redeemed': True,
                    'plan_code': coupon.get('plan_code'),
                    'order': order,
                    'message': '该兑换码已由您兑换过，会员权益已生效',
                }
            raise ValueError('该兑换码已被其他账号使用')
        if coupon.get('status') != 'issued':
            raise ValueError('兑换码状态异常，请联系客服')

    plan_code = str(coupon.get('plan_code') or '')
    plan = next((item for item in list_plans() if item.get('plan_code') == plan_code), None)
    if not plan:
        raise ValueError('兑换码关联的会员套餐无效')

    order_no, _order_id = create_pending_order(
        user_id=user_id,
        plan_code=plan_code,
        amount=float(plan.get('price') or 0),
        order_type='open',
        pay_method='douyin_coupon',
    )

    from payment_service import fulfill_wechat_order

    fulfill_wechat_order(
        order_no,
        transaction_id=str(coupon.get('douyin_order_id') or ''),
        notify_raw=f'douyin_coupon:{code}',
        pay_method='douyin_coupon',
    )

    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE douyin_coupons
            SET status = 'redeemed', user_id = ?, payment_order_no = ?,
                redeemed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE coupon_code = ?
            ''',
            [user_id, order_no, code],
        )
        connection.commit()

    order = get_order_by_order_no(order_no)
    return {
        'already_redeemed': False,
        'plan_code': plan_code,
        'plan_name': plan.get('plan_name'),
        'order': order,
        'message': f'兑换成功，已开通{plan.get("plan_name") or plan_code}并到账星鼎豆',
    }


def list_recent_coupons(limit: int = 50) -> list[dict[str, Any]]:
    ensure_douyin_coupon_tables()
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT coupon_id, coupon_code, douyin_order_id, plan_code, sku_name, status,
                   user_id, payment_order_no, redeemed_at, created_at
            FROM douyin_coupons
            ORDER BY coupon_id DESC
            LIMIT ?
            ''',
            [max(1, min(limit, 200))],
        ).fetchall()
    return rows_to_dicts(rows)
