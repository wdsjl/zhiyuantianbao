"""推广博主、扫码归因与订单分账服务。"""

from __future__ import annotations

import base64
import json
import os
import random
import string
import urllib.parse
import urllib.request
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts

WECHAT_API_HOST = 'https://api.weixin.qq.com'
DEFAULT_COMMISSION_RATE = 10.0


def ensure_referral_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_agents (
              agent_id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL UNIQUE,
              invite_code TEXT NOT NULL UNIQUE,
              display_name TEXT,
              status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
              commission_rate REAL NOT NULL DEFAULT 10,
              total_invites INTEGER NOT NULL DEFAULT 0,
              total_paid_orders INTEGER NOT NULL DEFAULT 0,
              total_commission REAL NOT NULL DEFAULT 0,
              settled_commission REAL NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_bindings (
              binding_id INTEGER PRIMARY KEY AUTOINCREMENT,
              invitee_user_id INTEGER NOT NULL UNIQUE,
              agent_id INTEGER NOT NULL,
              invite_code TEXT NOT NULL,
              bind_source TEXT NOT NULL DEFAULT 'poster',
              bound_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              first_paid_order_id INTEGER,
              FOREIGN KEY (invitee_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
              FOREIGN KEY (agent_id) REFERENCES referral_agents(agent_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_commissions (
              commission_id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_id INTEGER NOT NULL UNIQUE,
              order_no TEXT NOT NULL,
              agent_id INTEGER NOT NULL,
              invitee_user_id INTEGER NOT NULL,
              order_amount REAL NOT NULL DEFAULT 0,
              commission_rate REAL NOT NULL DEFAULT 0,
              commission_amount REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'settled', 'cancelled')),
              settled_at TEXT,
              remark TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (order_id) REFERENCES payment_orders(order_id) ON DELETE CASCADE,
              FOREIGN KEY (agent_id) REFERENCES referral_agents(agent_id) ON DELETE CASCADE,
              FOREIGN KEY (invitee_user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            '''
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES ('referral_commission_rate', ?)
            ON CONFLICT(setting_key) DO NOTHING
            ''',
            [str(DEFAULT_COMMISSION_RATE)]
        )
        connection.commit()


def _get_setting(key: str, default: str = '') -> str:
    with get_connection() as connection:
        row = connection.execute('SELECT setting_value FROM app_settings WHERE setting_key = ?', [key]).fetchone()
    return (row['setting_value'] if row else default) or default


def get_default_commission_rate() -> float:
    raw = _get_setting('referral_commission_rate', str(DEFAULT_COMMISSION_RATE))
    try:
        rate = float(raw)
    except ValueError:
        rate = DEFAULT_COMMISSION_RATE
    return max(0.0, min(rate, 100.0))


def get_referral_settings() -> dict[str, Any]:
    return {
        'commission_rate': get_default_commission_rate(),
    }


def save_referral_settings(commission_rate: float) -> dict[str, Any]:
    rate = max(0.0, min(float(commission_rate), 100.0))
    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES ('referral_commission_rate', ?)
            ON CONFLICT(setting_key) DO UPDATE SET
              setting_value = excluded.setting_value,
              updated_at = CURRENT_TIMESTAMP
            ''',
            [str(rate)]
        )
        connection.commit()
    return get_referral_settings()


def update_agent_commission_rate(agent_id: int, commission_rate: float) -> dict[str, Any]:
    ensure_referral_tables()
    rate = max(0.0, min(float(commission_rate), 100.0))
    with get_connection() as connection:
        agent = row_to_dict(connection.execute(
            'SELECT * FROM referral_agents WHERE agent_id = ?',
            [agent_id]
        ).fetchone())
        if not agent:
            raise ValueError('博主不存在')
        connection.execute(
            '''
            UPDATE referral_agents
            SET commission_rate = ?, updated_at = CURRENT_TIMESTAMP
            WHERE agent_id = ?
            ''',
            [rate, agent_id]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_agents WHERE agent_id = ?',
            [agent_id]
        ).fetchone())


def _generate_invite_code(connection) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = 'B' + ''.join(random.choices(alphabet, k=6))
        exists = connection.execute('SELECT 1 FROM referral_agents WHERE invite_code = ?', [code]).fetchone()
        if not exists:
            return code
    raise ValueError('邀请码生成失败，请重试')


def _get_access_token() -> str:
    appid = os.getenv('WECHAT_APPID', '')
    secret = os.getenv('WECHAT_SECRET', '')
    if not appid or not secret:
        raise ValueError('未配置 WECHAT_APPID / WECHAT_SECRET，无法生成推广海报二维码')
    query = urllib.parse.urlencode({
        'grant_type': 'client_credential',
        'appid': appid,
        'secret': secret,
    })
    with urllib.request.urlopen(f'{WECHAT_API_HOST}/cgi-bin/token?{query}', timeout=8) as response:
        data = json.loads(response.read().decode('utf-8'))
    if data.get('errcode'):
        raise ValueError(data.get('errmsg', '获取 access_token 失败'))
    token = data.get('access_token') or ''
    if not token:
        raise ValueError('获取 access_token 失败')
    return token


def get_agent_by_user_id(user_id: int) -> dict[str, Any] | None:
    ensure_referral_tables()
    with get_connection() as connection:
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_agents WHERE user_id = ?',
            [user_id]
        ).fetchone())


def get_agent_by_invite_code(invite_code: str) -> dict[str, Any] | None:
    ensure_referral_tables()
    code = (invite_code or '').strip().upper()
    if not code:
        return None
    with get_connection() as connection:
        return row_to_dict(connection.execute(
            "SELECT * FROM referral_agents WHERE invite_code = ? AND status = 'active'",
            [code]
        ).fetchone())


def register_agent(user_id: int, display_name: str | None = None) -> dict[str, Any]:
    ensure_referral_tables()
    with get_connection() as connection:
        existing = row_to_dict(connection.execute(
            'SELECT * FROM referral_agents WHERE user_id = ?',
            [user_id]
        ).fetchone())
        if existing:
            if display_name and display_name != existing.get('display_name'):
                connection.execute(
                    'UPDATE referral_agents SET display_name = ?, updated_at = CURRENT_TIMESTAMP WHERE agent_id = ?',
                    [display_name, existing['agent_id']]
                )
                connection.commit()
                existing['display_name'] = display_name
            return existing

        user = row_to_dict(connection.execute('SELECT name, phone FROM users WHERE user_id = ?', [user_id]).fetchone())
        if not user:
            raise ValueError('用户不存在')
        invite_code = _generate_invite_code(connection)
        label = display_name or user.get('name') or user.get('phone') or f'博主{user_id}'
        cursor = connection.execute(
            '''
            INSERT INTO referral_agents (user_id, invite_code, display_name, commission_rate)
            VALUES (?, ?, ?, ?)
            ''',
            [user_id, invite_code, label, get_default_commission_rate()]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_agents WHERE agent_id = ?',
            [cursor.lastrowid]
        ).fetchone())


def bind_invitee(invitee_user_id: int, invite_code: str, bind_source: str = 'poster') -> dict[str, Any] | None:
    from referral_p1 import attempt_bind_invitee
    result = attempt_bind_invitee(invitee_user_id, invite_code, bind_source)
    if result.get('success'):
        return result.get('binding')
    return None


def try_bind_on_login(user_id: int, invite_code: str | None, is_new_user: bool) -> dict[str, Any] | None:
    if not invite_code:
        return None
    from referral_p1 import attempt_bind_invitee
    result = attempt_bind_invitee(user_id, invite_code, 'poster' if is_new_user else 'scan')
    return result.get('binding') if result.get('success') else None


def get_binding_for_user(user_id: int) -> dict[str, Any] | None:
    ensure_referral_tables()
    with get_connection() as connection:
        return row_to_dict(connection.execute(
            '''
            SELECT b.*, a.display_name AS agent_name, a.invite_code AS agent_invite_code
            FROM referral_bindings b
            JOIN referral_agents a ON a.agent_id = b.agent_id
            WHERE b.invitee_user_id = ?
            ''',
            [user_id]
        ).fetchone())


def record_commission_for_order(order: dict[str, Any]) -> dict[str, Any] | None:
    ensure_referral_tables()
    if not order or order.get('pay_status') != 'paid':
        return None
    user_id = int(order['user_id'])
    order_id = int(order['order_id'])
    amount = float(order.get('amount') or 0)
    if amount <= 0:
        return None

    with get_connection() as connection:
        exists = connection.execute(
            'SELECT commission_id FROM referral_commissions WHERE order_id = ?',
            [order_id]
        ).fetchone()
        if exists:
            return row_to_dict(connection.execute(
                'SELECT * FROM referral_commissions WHERE order_id = ?',
                [order_id]
            ).fetchone())

        from referral_p1 import binding_valid_for_commission, is_user_blacklisted
        if is_user_blacklisted(user_id):
            return None

        binding = row_to_dict(connection.execute(
            'SELECT * FROM referral_bindings WHERE invitee_user_id = ?',
            [user_id]
        ).fetchone())
        if not binding or not binding_valid_for_commission(binding):
            return None

        agent = row_to_dict(connection.execute(
            'SELECT * FROM referral_agents WHERE agent_id = ?',
            [binding['agent_id']]
        ).fetchone())
        if not agent or agent.get('status') != 'active' or int(agent.get('is_blacklisted') or 0) == 1:
            return None

        rate = float(agent.get('commission_rate') or get_default_commission_rate())
        commission_amount = round(amount * rate / 100, 2)
        cursor = connection.execute(
            '''
            INSERT INTO referral_commissions (
              order_id, order_no, agent_id, invitee_user_id,
              order_amount, commission_rate, commission_amount, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ''',
            [order_id, order['order_no'], agent['agent_id'], user_id, amount, rate, commission_amount]
        )
        if not binding.get('first_paid_order_id'):
            connection.execute(
                'UPDATE referral_bindings SET first_paid_order_id = ? WHERE binding_id = ?',
                [order_id, binding['binding_id']]
            )
        connection.execute(
            '''
            UPDATE referral_agents
            SET total_paid_orders = total_paid_orders + 1,
                total_commission = total_commission + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE agent_id = ?
            ''',
            [commission_amount, agent['agent_id']]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_commissions WHERE commission_id = ?',
            [cursor.lastrowid]
        ).fetchone())


def cancel_commission_for_order(order_id: int, remark: str = '订单退款') -> None:
    ensure_referral_tables()
    with get_connection() as connection:
        commission = row_to_dict(connection.execute(
            "SELECT * FROM referral_commissions WHERE order_id = ? AND status != 'cancelled'",
            [order_id]
        ).fetchone())
        if not commission:
            return
        amount = float(commission.get('commission_amount') or 0)
        agent = row_to_dict(connection.execute(
            'SELECT * FROM referral_agents WHERE agent_id = ?',
            [commission['agent_id']]
        ).fetchone())
        if agent:
            settled = max(0.0, float(agent.get('settled_commission') or 0) - (amount if commission.get('status') == 'settled' else 0))
            total_commission = max(0.0, float(agent.get('total_commission') or 0) - amount)
            total_paid_orders = max(0, int(agent.get('total_paid_orders') or 0) - 1)
            connection.execute(
                '''
                UPDATE referral_agents
                SET settled_commission = ?, total_commission = ?, total_paid_orders = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = ?
                ''',
                [settled, total_commission, total_paid_orders, commission['agent_id']]
            )
        connection.execute(
            '''
            UPDATE referral_commissions
            SET status = 'cancelled', remark = ?, settled_at = CURRENT_TIMESTAMP
            WHERE commission_id = ?
            ''',
            [remark, commission['commission_id']]
        )
        connection.commit()


def settle_commission(commission_id: int, remark: str = '') -> dict[str, Any]:
    ensure_referral_tables()
    with get_connection() as connection:
        commission = row_to_dict(connection.execute(
            'SELECT * FROM referral_commissions WHERE commission_id = ?',
            [commission_id]
        ).fetchone())
        if not commission:
            raise ValueError('分账记录不存在')
        if commission.get('status') != 'pending':
            raise ValueError('仅待结算记录可确认分账')
        connection.execute(
            '''
            UPDATE referral_commissions
            SET status = 'settled', remark = ?, settled_at = CURRENT_TIMESTAMP
            WHERE commission_id = ?
            ''',
            [remark or '平台已确认分账', commission_id]
        )
        connection.execute(
            '''
            UPDATE referral_agents
            SET settled_commission = settled_commission + ?, updated_at = CURRENT_TIMESTAMP
            WHERE agent_id = ?
            ''',
            [commission['commission_amount'], commission['agent_id']]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_commissions WHERE commission_id = ?',
            [commission_id]
        ).fetchone())


def generate_poster_qrcode(invite_code: str) -> bytes:
    token = _get_access_token()
    payload = json.dumps({
        'scene': invite_code,
        'page': 'pages/home/home',
        'check_path': False,
        'env_version': 'release',
        'width': 430,
    }).encode('utf-8')
    request = urllib.request.Request(
        f'{WECHAT_API_HOST}/wxa/getwxacodeunlimit?access_token={token}',
        data=payload,
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        content = response.read()
    if content[:1] == b'{':
        data = json.loads(content.decode('utf-8'))
        raise ValueError(data.get('errmsg', '生成推广二维码失败'))
    return content


def get_agent_dashboard(user_id: int) -> dict[str, Any]:
    agent = register_agent(user_id)
    with get_connection() as connection:
        invitees = rows_to_dicts(connection.execute(
            '''
            SELECT b.bound_at, b.bind_source, u.user_id, u.name, u.phone, u.created_at,
                   (SELECT COUNT(*) FROM payment_orders po WHERE po.user_id = u.user_id AND po.pay_status = 'paid') AS paid_orders,
                   (SELECT IFNULL(SUM(po.amount), 0) FROM payment_orders po WHERE po.user_id = u.user_id AND po.pay_status = 'paid') AS paid_amount
            FROM referral_bindings b
            JOIN users u ON u.user_id = b.invitee_user_id
            WHERE b.agent_id = ?
            ORDER BY b.bound_at DESC
            LIMIT 200
            ''',
            [agent['agent_id']]
        ).fetchall())
        commissions = rows_to_dicts(connection.execute(
            '''
            SELECT c.*, u.name AS invitee_name, u.phone AS invitee_phone
            FROM referral_commissions c
            JOIN users u ON u.user_id = c.invitee_user_id
            WHERE c.agent_id = ?
            ORDER BY c.created_at DESC
            LIMIT 100
            ''',
            [agent['agent_id']]
        ).fetchall())
    pending_amount = sum(float(item.get('commission_amount') or 0) for item in commissions if item.get('status') == 'pending')
    from referral_p1 import get_agent_wallet
    wallet = get_agent_wallet(agent['agent_id'])
    return {
        'agent': agent,
        'invitees': invitees,
        'commissions': commissions,
        'pending_commission': round(pending_amount, 2),
        'wallet': wallet,
        'stats': {
            'scan_bind_users': agent.get('total_invites') or 0,
            'paid_orders': agent.get('total_paid_orders') or 0,
            'total_commission': agent.get('total_commission') or 0,
            'conversion_rate': round((int(agent.get('total_paid_orders') or 0) / max(int(agent.get('total_invites') or 0), 1)) * 100, 1),
        },
    }


def list_agents(keyword: str = '') -> list[dict[str, Any]]:
    ensure_referral_tables()
    sql = '''
    SELECT a.*, u.name AS user_name, u.phone AS user_phone, u.openid
    FROM referral_agents a
    JOIN users u ON u.user_id = a.user_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if keyword:
        sql += ' AND (a.display_name LIKE ? OR a.invite_code LIKE ? OR u.name LIKE ? OR u.phone LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY a.created_at DESC LIMIT 200'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def list_bindings(keyword: str = '') -> list[dict[str, Any]]:
    ensure_referral_tables()
    sql = '''
    SELECT b.*, a.display_name AS agent_name, a.invite_code AS agent_invite_code,
           u.name AS invitee_name, u.phone AS invitee_phone
    FROM referral_bindings b
    JOIN referral_agents a ON a.agent_id = b.agent_id
    JOIN users u ON u.user_id = b.invitee_user_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if keyword:
        sql += ' AND (a.display_name LIKE ? OR u.name LIKE ? OR u.phone LIKE ? OR b.invite_code LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY b.bound_at DESC LIMIT 300'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def list_commissions(keyword: str = '', status: str = '') -> list[dict[str, Any]]:
    ensure_referral_tables()
    sql = '''
    SELECT c.*, a.display_name AS agent_name, a.invite_code,
           u.name AS invitee_name, u.phone AS invitee_phone
    FROM referral_commissions c
    JOIN referral_agents a ON a.agent_id = c.agent_id
    JOIN users u ON u.user_id = c.invitee_user_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if keyword:
        sql += ' AND (c.order_no LIKE ? OR a.display_name LIKE ? OR u.name LIKE ? OR u.phone LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    if status:
        sql += ' AND c.status = ?'
        params.append(status)
    sql += ' ORDER BY c.created_at DESC LIMIT 300'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def poster_image_base64(invite_code: str) -> str:
    return base64.b64encode(generate_poster_qrcode(invite_code)).decode('ascii')
