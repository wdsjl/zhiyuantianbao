"""达人分销 P1：锁客加固、风控、核销日志、提现。"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from referral_service import (
    DEFAULT_COMMISSION_RATE,
    _get_setting,
    ensure_referral_tables,
    get_default_commission_rate,
    get_agent_by_invite_code,
)


def _ensure_column(connection, table: str, column: str, ddl: str) -> None:
    cols = [row['name'] for row in connection.execute(f'PRAGMA table_info({table})').fetchall()]
    if column not in cols:
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')


def ensure_referral_p1_tables() -> None:
    ensure_referral_tables()
    with get_connection() as connection:
        _ensure_column(connection, 'referral_agents', 'is_blacklisted', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'referral_agents', 'code_enabled', 'INTEGER NOT NULL DEFAULT 1')
        _ensure_column(connection, 'referral_agents', 'code_expires_at', 'TEXT')
        _ensure_column(connection, 'referral_agents', 'tags', "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, 'referral_agents', 'settlement_cycle', "TEXT NOT NULL DEFAULT 'monthly'")
        _ensure_column(connection, 'referral_agents', 'douyin_id', "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, 'referral_agents', 'fan_scale', "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, 'referral_bindings', 'expires_at', 'TEXT')
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_verify_logs (
              log_id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              agent_id INTEGER,
              invite_code TEXT,
              action TEXT NOT NULL,
              result TEXT NOT NULL,
              detail TEXT,
              ip TEXT,
              device_id TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_user_blacklist (
              user_id INTEGER PRIMARY KEY,
              reason TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_risk_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              agent_id INTEGER,
              user_id INTEGER,
              order_id INTEGER,
              risk_type TEXT NOT NULL,
              detail TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_free_claims (
              claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
              openid TEXT NOT NULL,
              user_id INTEGER,
              agent_id INTEGER,
              device_id TEXT,
              ip TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_free_claims_openid ON referral_free_claims(openid)'
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_withdrawals (
              withdrawal_id INTEGER PRIMARY KEY AUTOINCREMENT,
              agent_id INTEGER NOT NULL,
              amount REAL NOT NULL,
              pay_method TEXT NOT NULL DEFAULT 'wechat',
              pay_account TEXT NOT NULL,
              pay_name TEXT,
              status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'paid')),
              remark TEXT,
              reviewed_at TEXT,
              paid_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (agent_id) REFERENCES referral_agents(agent_id) ON DELETE CASCADE
            )
            '''
        )
        for key, value in [
            ('referral_attribution_mode', 'permanent'),
            ('referral_attribution_days', '30'),
            ('referral_settlement_cycle', 'monthly'),
            ('referral_min_withdraw_amount', '10'),
        ]:
            connection.execute(
                '''
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (?, ?) ON CONFLICT(setting_key) DO NOTHING
                ''',
                [key, value]
            )
        connection.commit()


def get_referral_policy_settings() -> dict[str, Any]:
    ensure_referral_p1_tables()
    mode = _get_setting('referral_attribution_mode', 'permanent')
    try:
        days = int(_get_setting('referral_attribution_days', '30'))
    except ValueError:
        days = 30
    return {
        'commission_rate': get_default_commission_rate(),
        'attribution_mode': mode if mode in ('permanent', 'timed') else 'permanent',
        'attribution_days': max(1, days),
        'settlement_cycle': _get_setting('referral_settlement_cycle', 'monthly'),
        'min_withdraw_amount': float(_get_setting('referral_min_withdraw_amount', '10') or 10),
    }


def save_referral_policy_settings(data: dict[str, Any]) -> dict[str, Any]:
    ensure_referral_p1_tables()
    mode = data.get('attribution_mode') or 'permanent'
    if mode not in ('permanent', 'timed'):
        mode = 'permanent'
    days = max(1, int(data.get('attribution_days') or 30))
    cycle = data.get('settlement_cycle') or 'monthly'
    min_amount = max(0.0, float(data.get('min_withdraw_amount') or 10))
    commission_rate = max(0.0, min(float(data.get('commission_rate') or DEFAULT_COMMISSION_RATE), 100.0))
    values = {
        'referral_attribution_mode': mode,
        'referral_attribution_days': str(days),
        'referral_settlement_cycle': cycle,
        'referral_min_withdraw_amount': str(min_amount),
        'referral_commission_rate': str(commission_rate),
    }
    with get_connection() as connection:
        for key, value in values.items():
            connection.execute(
                '''
                INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP
                ''',
                [key, value]
            )
        connection.commit()
    return get_referral_policy_settings()


def log_verify_event(
    action: str,
    result: str,
    invite_code: str = '',
    user_id: int | None = None,
    agent_id: int | None = None,
    detail: str = '',
    ip: str = '',
    device_id: str = '',
) -> None:
    ensure_referral_p1_tables()
    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO referral_verify_logs (user_id, agent_id, invite_code, action, result, detail, ip, device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [user_id, agent_id, invite_code, action, result, detail, ip, device_id]
        )
        connection.commit()


def is_user_blacklisted(user_id: int) -> bool:
    ensure_referral_p1_tables()
    with get_connection() as connection:
        row = connection.execute(
            'SELECT 1 FROM referral_user_blacklist WHERE user_id = ?',
            [user_id]
        ).fetchone()
    return bool(row)


def set_user_blacklist(user_id: int, blacklisted: bool, reason: str = '') -> None:
    ensure_referral_p1_tables()
    with get_connection() as connection:
        if blacklisted:
            connection.execute(
                '''
                INSERT INTO referral_user_blacklist (user_id, reason) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET reason = excluded.reason
                ''',
                [user_id, reason or '后台拉黑']
            )
        else:
            connection.execute('DELETE FROM referral_user_blacklist WHERE user_id = ?', [user_id])
        connection.commit()


def set_agent_blacklist(agent_id: int, blacklisted: bool) -> None:
    ensure_referral_p1_tables()
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE referral_agents
            SET is_blacklisted = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE agent_id = ?
            ''',
            [1 if blacklisted else 0, 'disabled' if blacklisted else 'active', agent_id]
        )
        connection.commit()


def resolve_agent(identifier: str) -> dict[str, Any] | None:
    ensure_referral_p1_tables()
    token = (identifier or '').strip().upper()
    if not token:
        return None
    agent = get_agent_by_invite_code(token)
    if agent:
        return agent
    if token.isdigit():
        with get_connection() as connection:
            agent = row_to_dict(connection.execute(
                "SELECT * FROM referral_agents WHERE agent_id = ? AND status = 'active'",
                [int(token)]
            ).fetchone())
            if agent and int(agent.get('is_blacklisted') or 0) == 1:
                return None
            return agent
    return None


def validate_agent_code(agent: dict[str, Any] | None) -> tuple[bool, str]:
    if not agent:
        return False, '推广码无效或已停用'
    if int(agent.get('is_blacklisted') or 0) == 1 or agent.get('status') != 'active':
        return False, '该达人已停止合作'
    if int(agent.get('code_enabled') or 1) != 1:
        return False, '推广码已停用'
    expires_at = agent.get('code_expires_at')
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at.replace('Z', '')) < datetime.now():
                return False, '推广码已过期'
        except ValueError:
            pass
    return True, ''


def _calc_binding_expires_at() -> str | None:
    policy = get_referral_policy_settings()
    if policy['attribution_mode'] != 'timed':
        return None
    return (datetime.now() + timedelta(days=policy['attribution_days'])).isoformat(timespec='seconds')


def is_binding_active(binding: dict[str, Any] | None) -> bool:
    if not binding:
        return False
    expires_at = binding.get('expires_at')
    if not expires_at:
        return True
    try:
        return datetime.fromisoformat(expires_at.replace('Z', '')) >= datetime.now()
    except ValueError:
        return True


def attempt_bind_invitee(
    invitee_user_id: int,
    invite_code: str,
    bind_source: str = 'poster',
    ip: str = '',
    device_id: str = '',
) -> dict[str, Any]:
    ensure_referral_p1_tables()
    code = (invite_code or '').strip().upper()
    if not code:
        return {'success': False, 'reason': 'empty_code', 'message': '缺少达人推广码'}

    if is_user_blacklisted(invitee_user_id):
        log_verify_event('bind', 'blocked_user', code, invitee_user_id, detail='用户黑名单', ip=ip, device_id=device_id)
        return {'success': False, 'reason': 'user_blacklisted', 'message': '账号异常，无法绑定'}

    agent = resolve_agent(code)
    ok, msg = validate_agent_code(agent)
    if not ok:
        log_verify_event('bind', 'invalid_code', code, invitee_user_id, agent and agent.get('agent_id'), msg, ip, device_id)
        return {'success': False, 'reason': 'invalid_code', 'message': msg}

    if int(agent['user_id']) == int(invitee_user_id):
        return {'success': False, 'reason': 'self_bind', 'message': '不能绑定自己的推广码'}

    with get_connection() as connection:
        existing = row_to_dict(connection.execute(
            '''
            SELECT b.*, a.display_name AS agent_name, a.invite_code AS bound_code
            FROM referral_bindings b
            JOIN referral_agents a ON a.agent_id = b.agent_id
            WHERE b.invitee_user_id = ?
            ''',
            [invitee_user_id]
        ).fetchone())
        if existing:
            if int(existing['agent_id']) == int(agent['agent_id']):
                log_verify_event('bind', 'already_bound_same', code, invitee_user_id, agent['agent_id'], ip=ip, device_id=device_id)
                return {
                    'success': True,
                    'reason': 'already_bound_same',
                    'message': f'您已绑定{existing.get("agent_name") or "该达人"}',
                    'binding': existing,
                }
            log_verify_event('bind', 'already_bound_other', code, invitee_user_id, agent['agent_id'], ip=ip, device_id=device_id)
            return {
                'success': False,
                'reason': 'already_bound_other',
                'message': f'已绑定其他渠道（{existing.get("agent_name") or existing.get("bound_code")}），无法更换',
                'binding': existing,
            }

        expires_at = _calc_binding_expires_at()
        cursor = connection.execute(
            '''
            INSERT INTO referral_bindings (invitee_user_id, agent_id, invite_code, bind_source, expires_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            [invitee_user_id, agent['agent_id'], agent['invite_code'], bind_source, expires_at]
        )
        connection.execute(
            'UPDATE referral_agents SET total_invites = total_invites + 1, updated_at = CURRENT_TIMESTAMP WHERE agent_id = ?',
            [agent['agent_id']]
        )
        connection.commit()
        binding = row_to_dict(connection.execute(
            'SELECT * FROM referral_bindings WHERE binding_id = ?',
            [cursor.lastrowid]
        ).fetchone())

    log_verify_event('bind', 'success', agent['invite_code'], invitee_user_id, agent['agent_id'], ip=ip, device_id=device_id)
    return {
        'success': True,
        'reason': 'bound',
        'message': f'您已通过{agent.get("display_name") or "达人老师"}的渠道领取专属权益',
        'binding': binding,
        'agent': {'agent_id': agent['agent_id'], 'display_name': agent.get('display_name'), 'invite_code': agent['invite_code']},
    }


def claim_free_trial_once(
    user_id: int,
    openid: str,
    agent_id: int | None = None,
    device_id: str = '',
    ip: str = '',
) -> dict[str, Any]:
    ensure_referral_p1_tables()
    openid = (openid or '').strip()
    if not openid:
        return {'claimed': False, 'reason': 'no_openid', 'message': '请先微信登录'}
    with get_connection() as connection:
        exists = connection.execute(
            'SELECT claim_id FROM referral_free_claims WHERE openid = ?',
            [openid]
        ).fetchone()
        if exists:
            return {'claimed': False, 'reason': 'already_claimed', 'message': '已领取过免费体验，不可重复领取'}
        connection.execute(
            '''
            INSERT INTO referral_free_claims (openid, user_id, agent_id, device_id, ip)
            VALUES (?, ?, ?, ?, ?)
            ''',
            [openid, user_id, agent_id, device_id, ip]
        )
        connection.commit()
    return {'claimed': True, 'message': '专属体验权益已记录'}


def trace_attribution(keyword: str) -> dict[str, Any]:
    ensure_referral_p1_tables()
    keyword = (keyword or '').strip()
    if not keyword:
        return {'bindings': [], 'commissions': [], 'orders': []}
    like = f'%{keyword}%'
    with get_connection() as connection:
        bindings = rows_to_dicts(connection.execute(
            '''
            SELECT b.*, a.display_name AS agent_name, a.invite_code AS agent_invite_code, a.agent_id,
                   u.name AS invitee_name, u.phone AS invitee_phone, u.user_id
            FROM referral_bindings b
            JOIN referral_agents a ON a.agent_id = b.agent_id
            JOIN users u ON u.user_id = b.invitee_user_id
            WHERE CAST(u.user_id AS TEXT) = ? OR u.phone LIKE ? OR a.invite_code LIKE ? OR CAST(a.agent_id AS TEXT) = ?
            ORDER BY b.bound_at DESC LIMIT 50
            ''',
            [keyword, like, like, keyword]
        ).fetchall())
        commissions = rows_to_dicts(connection.execute(
            '''
            SELECT c.*, a.display_name AS agent_name, u.name AS invitee_name, u.phone AS invitee_phone
            FROM referral_commissions c
            JOIN referral_agents a ON a.agent_id = c.agent_id
            JOIN users u ON u.user_id = c.invitee_user_id
            WHERE c.order_no LIKE ? OR CAST(u.user_id AS TEXT) = ? OR u.phone LIKE ?
            ORDER BY c.created_at DESC LIMIT 50
            ''',
            [like, keyword, like]
        ).fetchall())
        orders = rows_to_dicts(connection.execute(
            '''
            SELECT po.*, u.name AS user_name, u.phone
            FROM payment_orders po
            JOIN users u ON u.user_id = po.user_id
            WHERE po.order_no LIKE ? OR CAST(u.user_id AS TEXT) = ? OR u.phone LIKE ?
            ORDER BY po.created_at DESC LIMIT 50
            ''',
            [like, keyword, like]
        ).fetchall())
    return {'bindings': bindings, 'commissions': commissions, 'orders': orders}


def get_agent_wallet(agent_id: int) -> dict[str, Any]:
    ensure_referral_p1_tables()
    with get_connection() as connection:
        agent = row_to_dict(connection.execute('SELECT * FROM referral_agents WHERE agent_id = ?', [agent_id]).fetchone())
        if not agent:
            raise ValueError('达人不存在')
        pending = connection.execute(
            "SELECT IFNULL(SUM(commission_amount), 0) AS total FROM referral_commissions WHERE agent_id = ? AND status = 'pending'",
            [agent_id]
        ).fetchone()['total']
        settled = float(agent.get('settled_commission') or 0)
        withdrawn = connection.execute(
            "SELECT IFNULL(SUM(amount), 0) AS total FROM referral_withdrawals WHERE agent_id = ? AND status IN ('approved', 'paid')",
            [agent_id]
        ).fetchone()['total']
        pending_withdraw = connection.execute(
            "SELECT IFNULL(SUM(amount), 0) AS total FROM referral_withdrawals WHERE agent_id = ? AND status = 'pending'",
            [agent_id]
        ).fetchone()['total']
    available = max(0.0, round(float(settled) - float(withdrawn) - float(pending_withdraw), 2))
    return {
        'pending_commission': round(float(pending), 2),
        'settled_commission': round(settled, 2),
        'withdrawn_amount': round(float(withdrawn), 2),
        'available_amount': available,
        'pending_withdraw_amount': round(float(pending_withdraw), 2),
    }


def create_withdrawal(agent_id: int, amount: float, pay_method: str, pay_account: str, pay_name: str = '') -> dict[str, Any]:
    ensure_referral_p1_tables()
    policy = get_referral_policy_settings()
    amount = round(float(amount), 2)
    if amount < policy['min_withdraw_amount']:
        raise ValueError(f'最低提现金额为 ¥{policy["min_withdraw_amount"]}')
    wallet = get_agent_wallet(agent_id)
    if amount > wallet['available_amount']:
        raise ValueError('可提现余额不足')
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO referral_withdrawals (agent_id, amount, pay_method, pay_account, pay_name)
            VALUES (?, ?, ?, ?, ?)
            ''',
            [agent_id, amount, pay_method, pay_account, pay_name]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_withdrawals WHERE withdrawal_id = ?',
            [cursor.lastrowid]
        ).fetchone())


def list_withdrawals(keyword: str = '', status: str = '') -> list[dict[str, Any]]:
    ensure_referral_p1_tables()
    sql = '''
    SELECT w.*, a.display_name, a.invite_code, u.phone, u.name AS user_name
    FROM referral_withdrawals w
    JOIN referral_agents a ON a.agent_id = w.agent_id
    JOIN users u ON u.user_id = a.user_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if keyword:
        sql += ' AND (a.display_name LIKE ? OR a.invite_code LIKE ? OR u.phone LIKE ? OR w.pay_account LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    if status:
        sql += ' AND w.status = ?'
        params.append(status)
    sql += ' ORDER BY w.created_at DESC LIMIT 200'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def review_withdrawal(withdrawal_id: int, action: str, remark: str = '') -> dict[str, Any]:
    ensure_referral_p1_tables()
    if action not in ('approved', 'rejected', 'paid'):
        raise ValueError('无效审核动作')
    with get_connection() as connection:
        row = row_to_dict(connection.execute(
            'SELECT * FROM referral_withdrawals WHERE withdrawal_id = ?',
            [withdrawal_id]
        ).fetchone())
        if not row:
            raise ValueError('提现申请不存在')
        if row['status'] not in ('pending', 'approved') and action != 'paid':
            raise ValueError('当前状态不可审核')
        reviewed_at = datetime.now().isoformat(timespec='seconds')
        paid_at = reviewed_at if action == 'paid' else row.get('paid_at')
        connection.execute(
            '''
            UPDATE referral_withdrawals
            SET status = ?, remark = ?, reviewed_at = ?, paid_at = COALESCE(?, paid_at)
            WHERE withdrawal_id = ?
            ''',
            [action, remark, reviewed_at, paid_at, withdrawal_id]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_withdrawals WHERE withdrawal_id = ?',
            [withdrawal_id]
        ).fetchone())


def adjust_commission_amount(commission_id: int, commission_amount: float, remark: str = '') -> dict[str, Any]:
    ensure_referral_p1_tables()
    amount = round(float(commission_amount), 2)
    with get_connection() as connection:
        commission = row_to_dict(connection.execute(
            'SELECT * FROM referral_commissions WHERE commission_id = ?',
            [commission_id]
        ).fetchone())
        if not commission:
            raise ValueError('分账记录不存在')
        if commission.get('status') == 'cancelled':
            raise ValueError('已取消记录不可调整')
        old_amount = float(commission.get('commission_amount') or 0)
        diff = amount - old_amount
        connection.execute(
            'UPDATE referral_commissions SET commission_amount = ?, remark = ? WHERE commission_id = ?',
            [amount, remark or commission.get('remark') or '后台手动调整', commission_id]
        )
        connection.execute(
            'UPDATE referral_agents SET total_commission = total_commission + ?, updated_at = CURRENT_TIMESTAMP WHERE agent_id = ?',
            [diff, commission['agent_id']]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_commissions WHERE commission_id = ?',
            [commission_id]
        ).fetchone())


def export_referral_csv() -> str:
    ensure_referral_p1_tables()
    rows = list_commissions_for_export()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['订单号', '用户ID', '用户手机', '达人ID', '达人名', '邀请码', '订单金额', '佣金比例', '佣金金额', '状态', '时间'])
    for item in rows:
        writer.writerow([
            item.get('order_no'), item.get('invitee_user_id'), item.get('invitee_phone'),
            item.get('agent_id'), item.get('agent_name'), item.get('invite_code'),
            item.get('order_amount'), item.get('commission_rate'), item.get('commission_amount'),
            item.get('status'), item.get('created_at'),
        ])
    return buffer.getvalue()


def list_commissions_for_export() -> list[dict[str, Any]]:
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(
            '''
            SELECT c.*, a.display_name AS agent_name, a.invite_code, a.agent_id, u.phone AS invitee_phone
            FROM referral_commissions c
            JOIN referral_agents a ON a.agent_id = c.agent_id
            JOIN users u ON u.user_id = c.invitee_user_id
            ORDER BY c.created_at DESC LIMIT 5000
            '''
        ).fetchall())


def list_verify_logs(limit: int = 100) -> list[dict[str, Any]]:
    ensure_referral_p1_tables()
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(
            'SELECT * FROM referral_verify_logs ORDER BY created_at DESC LIMIT ?',
            [limit]
        ).fetchall())


def binding_valid_for_commission(binding: dict[str, Any]) -> bool:
    policy = get_referral_policy_settings()
    if policy['attribution_mode'] == 'permanent':
        return True
    return is_binding_active(binding)
