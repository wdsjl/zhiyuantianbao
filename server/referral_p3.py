"""达人分销 P3：等级体系、全局大盘、FAQ、达人跟进任务、微信自动打款。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from referral_p1 import ensure_referral_p1_tables
from referral_p2 import ensure_referral_p2_tables

DEFAULT_LEVELS = [
    {'level_key': 'L1', 'level_name': '新手达人', 'min_paid_orders': 0, 'rate_bonus': 0.0},
    {'level_key': 'L2', 'level_name': '进阶达人', 'min_paid_orders': 5, 'rate_bonus': 1.0},
    {'level_key': 'L3', 'level_name': '资深达人', 'min_paid_orders': 20, 'rate_bonus': 2.0},
    {'level_key': 'L4', 'level_name': '金牌达人', 'min_paid_orders': 50, 'rate_bonus': 3.0},
]

DEFAULT_FAQS = [
    {
        'question': '如何成为推广达人？',
        'answer': '在小程序「我的」进入「达人推广中心」，系统会自动为您生成专属邀请码与推广海报。',
        'sort_order': 1,
    },
    {
        'question': '用户扫码后如何算我的推广？',
        'answer': '用户通过您的海报或分享链接进入小程序并完成绑定后，即归属为您的推广用户。一人一达人，绑定后不可更换渠道。',
        'sort_order': 2,
    },
    {
        'question': '佣金什么时候到账？',
        'answer': '用户支付成功后系统生成待分账记录，平台确认结算后计入您的可提现余额。结算周期以后台配置为准（日结/周结/月结）。',
        'sort_order': 3,
    },
    {
        'question': '如何提现？',
        'answer': '在推广中心点击「提现中心」，填写收款方式与账号提交申请。审核通过后平台打款，微信收款可开启自动打款。',
        'sort_order': 4,
    },
    {
        'question': '达人等级有什么用？',
        'answer': '等级根据您带来的付费订单数自动提升，高等级可在基础佣金比例上获得额外加成（如 +1%～+3%）。',
        'sort_order': 5,
    },
]

DEFAULT_DOUYIN_INVITE_TEMPLATE = (
    '您好，我是智愿填报合作运营。如您已有合作意向，欢迎了解我们的达人分销计划：'
    '专属海报、推广物料与佣金分账。如需详聊请回复「合作」。'
)

FOLLOW_UP_COMPLIANCE_NOTICE = (
    '本功能仅用于内部跟进已授权或已建立合作意向的达人，系统不会向抖音自动发送任何消息。'
    '禁止将生成的任务用于未授权名单的批量私信或骚扰式营销；对外联系须人工一对一沟通，并遵守平台规则与个人信息保护法。'
)


def _ensure_column(connection, table: str, column: str, ddl: str) -> None:
    cols = [row['name'] for row in connection.execute(f'PRAGMA table_info({table})').fetchall()]
    if column not in cols:
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')


def _get_setting(key: str, default: str = '') -> str:
    with get_connection() as connection:
        row = connection.execute('SELECT setting_value FROM app_settings WHERE setting_key = ?', [key]).fetchone()
    return (row['setting_value'] if row else default) or default


def ensure_referral_p3_tables() -> None:
    ensure_referral_p2_tables()
    with get_connection() as connection:
        _ensure_column(connection, 'referral_agents', 'agent_level', "TEXT NOT NULL DEFAULT 'L1'")
        _ensure_column(connection, 'referral_agents', 'level_locked', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(connection, 'referral_withdrawals', 'transfer_bill_no', 'TEXT')
        _ensure_column(connection, 'referral_withdrawals', 'transfer_status', 'TEXT')
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_faqs (
              faq_id INTEGER PRIMARY KEY AUTOINCREMENT,
              question TEXT NOT NULL,
              answer TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0,
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS referral_douyin_invites (
              invite_id INTEGER PRIMARY KEY AUTOINCREMENT,
              agent_id INTEGER NOT NULL,
              douyin_id TEXT NOT NULL DEFAULT '',
              invite_message TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'sent', 'joined', 'rejected', 'skipped')),
              remark TEXT,
              sent_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (agent_id) REFERENCES referral_agents(agent_id) ON DELETE CASCADE
            )
            '''
        )
        for key, value in [
            ('referral_level_config', json.dumps(DEFAULT_LEVELS, ensure_ascii=False)),
            ('referral_auto_pay_enabled', '0'),
            ('referral_douyin_invite_template', DEFAULT_DOUYIN_INVITE_TEMPLATE),
        ]:
            connection.execute(
                '''
                INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
                ON CONFLICT(setting_key) DO NOTHING
                ''',
                [key, value]
            )
        faq_count = connection.execute('SELECT COUNT(*) AS c FROM referral_faqs').fetchone()['c']
        if faq_count == 0:
            for item in DEFAULT_FAQS:
                connection.execute(
                    '''
                    INSERT INTO referral_faqs (question, answer, sort_order)
                    VALUES (?, ?, ?)
                    ''',
                    [item['question'], item['answer'], item['sort_order']]
                )
        connection.commit()


def get_level_config() -> list[dict[str, Any]]:
    ensure_referral_p3_tables()
    raw = _get_setting('referral_level_config', '')
    try:
        levels = json.loads(raw) if raw else DEFAULT_LEVELS
    except json.JSONDecodeError:
        levels = DEFAULT_LEVELS
    if not levels:
        levels = DEFAULT_LEVELS
    return sorted(levels, key=lambda item: int(item.get('min_paid_orders') or 0))


def save_level_config(levels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ensure_referral_p3_tables()
    normalized = []
    for item in levels:
        normalized.append({
            'level_key': str(item.get('level_key') or '').strip() or f'L{len(normalized) + 1}',
            'level_name': str(item.get('level_name') or '').strip() or '达人',
            'min_paid_orders': max(0, int(item.get('min_paid_orders') or 0)),
            'rate_bonus': max(0.0, float(item.get('rate_bonus') or 0)),
        })
    normalized = sorted(normalized, key=lambda row: row['min_paid_orders'])
    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP
            ''',
            ['referral_level_config', json.dumps(normalized, ensure_ascii=False)]
        )
        connection.commit()
    sync_all_agent_levels()
    return normalized


def resolve_level_for_orders(paid_orders: int, levels: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    levels = levels or get_level_config()
    current = levels[0]
    next_level = None
    for index, level in enumerate(levels):
        if paid_orders >= int(level.get('min_paid_orders') or 0):
            current = level
            next_level = levels[index + 1] if index + 1 < len(levels) else None
    progress = 100
    orders_to_next = 0
    if next_level:
        start = int(current.get('min_paid_orders') or 0)
        target = int(next_level.get('min_paid_orders') or 0)
        span = max(target - start, 1)
        progress = min(100, round(((paid_orders - start) / span) * 100, 1))
        orders_to_next = max(0, target - paid_orders)
    return {
        'level_key': current.get('level_key'),
        'level_name': current.get('level_name'),
        'rate_bonus': float(current.get('rate_bonus') or 0),
        'min_paid_orders': int(current.get('min_paid_orders') or 0),
        'next_level_key': next_level.get('level_key') if next_level else None,
        'next_level_name': next_level.get('level_name') if next_level else None,
        'orders_to_next': orders_to_next,
        'progress_percent': progress,
    }


def get_agent_level_info(agent: dict[str, Any]) -> dict[str, Any]:
    ensure_referral_p3_tables()
    paid_orders = int(agent.get('total_paid_orders') or 0)
    levels = get_level_config()
    level = resolve_level_for_orders(paid_orders, levels)
    base_rate = float(agent.get('commission_rate') or 0)
    effective_rate = min(100.0, round(base_rate + float(level.get('rate_bonus') or 0), 2))
    return {
        **level,
        'agent_level': agent.get('agent_level') or level.get('level_key'),
        'base_commission_rate': base_rate,
        'effective_commission_rate': effective_rate,
        'total_paid_orders': paid_orders,
        'levels': levels,
    }


def sync_agent_level(agent_id: int) -> dict[str, Any]:
    ensure_referral_p3_tables()
    with get_connection() as connection:
        agent = row_to_dict(connection.execute('SELECT * FROM referral_agents WHERE agent_id = ?', [agent_id]).fetchone())
        if not agent:
            raise ValueError('达人不存在')
        if int(agent.get('level_locked') or 0):
            return get_agent_level_info(agent)
        level = resolve_level_for_orders(int(agent.get('total_paid_orders') or 0))
        connection.execute(
            '''
            UPDATE referral_agents
            SET agent_level = ?, updated_at = CURRENT_TIMESTAMP
            WHERE agent_id = ?
            ''',
            [level['level_key'], agent_id]
        )
        connection.commit()
        agent = row_to_dict(connection.execute('SELECT * FROM referral_agents WHERE agent_id = ?', [agent_id]).fetchone())
    return get_agent_level_info(agent or {})


def sync_all_agent_levels() -> int:
    ensure_referral_p3_tables()
    with get_connection() as connection:
        agents = rows_to_dicts(connection.execute('SELECT agent_id FROM referral_agents').fetchall())
    updated = 0
    for item in agents:
        sync_agent_level(int(item['agent_id']))
        updated += 1
    return updated


def set_agent_level(agent_id: int, level_key: str, locked: bool = True) -> dict[str, Any]:
    ensure_referral_p3_tables()
    with get_connection() as connection:
        agent = row_to_dict(connection.execute('SELECT * FROM referral_agents WHERE agent_id = ?', [agent_id]).fetchone())
        if not agent:
            raise ValueError('达人不存在')
        connection.execute(
            '''
            UPDATE referral_agents
            SET agent_level = ?, level_locked = ?, updated_at = CURRENT_TIMESTAMP
            WHERE agent_id = ?
            ''',
            [level_key, 1 if locked else 0, agent_id]
        )
        connection.commit()
        agent = row_to_dict(connection.execute('SELECT * FROM referral_agents WHERE agent_id = ?', [agent_id]).fetchone())
    return get_agent_level_info(agent or {})


def get_global_stats(days: int = 30) -> dict[str, Any]:
    ensure_referral_p3_tables()
    days = max(1, min(int(days or 30), 365))
    since = (datetime.now() - timedelta(days=days)).isoformat(timespec='seconds')
    with get_connection() as connection:
        agents_total = connection.execute('SELECT COUNT(*) AS c FROM referral_agents').fetchone()['c']
        agents_active = connection.execute(
            "SELECT COUNT(*) AS c FROM referral_agents WHERE status = 'active' AND IFNULL(is_blacklisted, 0) = 0"
        ).fetchone()['c']
        binds_total = connection.execute('SELECT COUNT(*) AS c FROM referral_bindings').fetchone()['c']
        binds_range = connection.execute(
            'SELECT COUNT(*) AS c FROM referral_bindings WHERE bound_at >= ?',
            [since]
        ).fetchone()['c']
        paid_orders = connection.execute(
            '''
            SELECT COUNT(*) AS c, IFNULL(SUM(order_amount), 0) AS amount
            FROM referral_commissions
            WHERE status != 'cancelled' AND created_at >= ?
            ''',
            [since]
        ).fetchone()
        commission = connection.execute(
            '''
            SELECT
              IFNULL(SUM(CASE WHEN status = 'pending' THEN commission_amount ELSE 0 END), 0) AS pending,
              IFNULL(SUM(CASE WHEN status = 'settled' THEN commission_amount ELSE 0 END), 0) AS settled,
              IFNULL(SUM(commission_amount), 0) AS total
            FROM referral_commissions
            WHERE status != 'cancelled' AND created_at >= ?
            ''',
            [since]
        ).fetchone()
        withdrawals = connection.execute(
            '''
            SELECT
              IFNULL(SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END), 0) AS pending,
              IFNULL(SUM(CASE WHEN status IN ('approved', 'paid') THEN amount ELSE 0 END), 0) AS approved_or_paid
            FROM referral_withdrawals
            WHERE created_at >= ?
            ''',
            [since]
        ).fetchone()
        daily_binds = rows_to_dicts(connection.execute(
            '''
            SELECT substr(bound_at, 1, 10) AS day, COUNT(*) AS binds
            FROM referral_bindings
            WHERE bound_at >= ?
            GROUP BY substr(bound_at, 1, 10)
            ORDER BY day ASC
            ''',
            [since]
        ).fetchall())
        daily_orders = rows_to_dicts(connection.execute(
            '''
            SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS orders, IFNULL(SUM(commission_amount), 0) AS commission
            FROM referral_commissions
            WHERE status != 'cancelled' AND created_at >= ?
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day ASC
            ''',
            [since]
        ).fetchall())
        top_agents = rows_to_dicts(connection.execute(
            '''
            SELECT a.agent_id, a.display_name, a.invite_code, a.agent_level, a.total_invites, a.total_paid_orders,
                   IFNULL(SUM(c.commission_amount), 0) AS range_commission
            FROM referral_agents a
            LEFT JOIN referral_commissions c ON c.agent_id = a.agent_id AND c.status != 'cancelled' AND c.created_at >= ?
            GROUP BY a.agent_id
            ORDER BY range_commission DESC, a.total_paid_orders DESC
            LIMIT 10
            ''',
            [since]
        ).fetchall())
        level_distribution = rows_to_dicts(connection.execute(
            '''
            SELECT agent_level, COUNT(*) AS count
            FROM referral_agents
            GROUP BY agent_level
            ORDER BY agent_level ASC
            '''
        ).fetchall())
        invite_pending = connection.execute(
            "SELECT COUNT(*) AS c FROM referral_douyin_invites WHERE status = 'pending'"
        ).fetchone()['c']
    orders_count = int(paid_orders['c'] or 0)
    binds_count = int(binds_range or 0)
    return {
        'days': days,
        'agents_total': int(agents_total or 0),
        'agents_active': int(agents_active or 0),
        'binds_total': int(binds_total or 0),
        'binds_range': binds_count,
        'paid_orders_range': orders_count,
        'order_amount_range': round(float(paid_orders['amount'] or 0), 2),
        'commission_pending': round(float(commission['pending'] or 0), 2),
        'commission_settled': round(float(commission['settled'] or 0), 2),
        'commission_total': round(float(commission['total'] or 0), 2),
        'withdraw_pending': round(float(withdrawals['pending'] or 0), 2),
        'withdraw_approved_or_paid': round(float(withdrawals['approved_or_paid'] or 0), 2),
        'conversion_rate': round((orders_count / max(binds_count, 1)) * 100, 1),
        'daily_binds': daily_binds,
        'daily_orders': daily_orders,
        'top_agents': top_agents,
        'level_distribution': level_distribution,
        'douyin_invites_pending': int(invite_pending or 0),
    }


def list_faqs(active_only: bool = True) -> list[dict[str, Any]]:
    ensure_referral_p3_tables()
    sql = 'SELECT * FROM referral_faqs WHERE 1=1'
    if active_only:
        sql += ' AND is_active = 1'
    sql += ' ORDER BY sort_order ASC, faq_id ASC'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql).fetchall())


def save_faq(faq_id: int | None, question: str, answer: str, sort_order: int = 0, is_active: int = 1) -> dict[str, Any]:
    ensure_referral_p3_tables()
    with get_connection() as connection:
        if faq_id:
            connection.execute(
                '''
                UPDATE referral_faqs
                SET question = ?, answer = ?, sort_order = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE faq_id = ?
                ''',
                [question, answer, sort_order, is_active, faq_id]
            )
            target_id = faq_id
        else:
            cursor = connection.execute(
                '''
                INSERT INTO referral_faqs (question, answer, sort_order, is_active)
                VALUES (?, ?, ?, ?)
                ''',
                [question, answer, sort_order, is_active]
            )
            target_id = cursor.lastrowid
        connection.commit()
        return row_to_dict(connection.execute('SELECT * FROM referral_faqs WHERE faq_id = ?', [target_id]).fetchone())


def delete_faq(faq_id: int) -> None:
    ensure_referral_p3_tables()
    with get_connection() as connection:
        connection.execute('DELETE FROM referral_faqs WHERE faq_id = ?', [faq_id])
        connection.commit()


def get_douyin_invite_template() -> str:
    return _get_setting('referral_douyin_invite_template', DEFAULT_DOUYIN_INVITE_TEMPLATE)


def save_douyin_invite_template(template: str) -> str:
    ensure_referral_p3_tables()
    value = (template or '').strip() or DEFAULT_DOUYIN_INVITE_TEMPLATE
    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP
            ''',
            ['referral_douyin_invite_template', value]
        )
        connection.commit()
    return value


def build_douyin_invite_message(agent: dict[str, Any], template: str | None = None) -> str:
    template = (template or get_douyin_invite_template()).strip()
    name = agent.get('display_name') or '老师'
    douyin = agent.get('douyin_id') or ''
    invite_code = agent.get('invite_code') or ''
    return (
        template.replace('{昵称}', str(name))
        .replace('{抖音号}', str(douyin))
        .replace('{邀请码}', str(invite_code))
    )


def list_douyin_invites(status: str = '', keyword: str = '') -> list[dict[str, Any]]:
    ensure_referral_p3_tables()
    sql = '''
    SELECT i.*, a.display_name, a.invite_code, a.douyin_id AS agent_douyin_id, a.fan_scale, a.tags
    FROM referral_douyin_invites i
    JOIN referral_agents a ON a.agent_id = i.agent_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if status:
        sql += ' AND i.status = ?'
        params.append(status)
    if keyword:
        like = f'%{keyword}%'
        sql += ' AND (a.display_name LIKE ? OR a.douyin_id LIKE ? OR i.douyin_id LIKE ? OR a.invite_code LIKE ?)'
        params.extend([like, like, like, like])
    sql += ' ORDER BY i.created_at DESC LIMIT 200'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def queue_douyin_invite(agent_id: int, remark: str = '') -> dict[str, Any]:
    ensure_referral_p3_tables()
    with get_connection() as connection:
        agent = row_to_dict(connection.execute('SELECT * FROM referral_agents WHERE agent_id = ?', [agent_id]).fetchone())
        if not agent:
            raise ValueError('达人不存在')
        existing = connection.execute(
            "SELECT invite_id FROM referral_douyin_invites WHERE agent_id = ? AND status IN ('pending', 'sent')",
            [agent_id]
        ).fetchone()
        if existing:
            return row_to_dict(connection.execute(
                'SELECT * FROM referral_douyin_invites WHERE invite_id = ?',
                [existing['invite_id']]
            ).fetchone())
        message = build_douyin_invite_message(agent)
        cursor = connection.execute(
            '''
            INSERT INTO referral_douyin_invites (agent_id, douyin_id, invite_message, status, remark)
            VALUES (?, ?, ?, 'pending', ?)
            ''',
            [agent_id, agent.get('douyin_id') or '', message, remark]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_douyin_invites WHERE invite_id = ?',
            [cursor.lastrowid]
        ).fetchone())


def batch_queue_douyin_invites(limit: int = 50) -> dict[str, Any]:
    ensure_referral_p3_tables()
    limit = max(1, min(int(limit or 50), 200))
    with get_connection() as connection:
        agents = rows_to_dicts(connection.execute(
            '''
            SELECT a.*
            FROM referral_agents a
            WHERE IFNULL(a.douyin_id, '') != ''
              AND IFNULL(a.is_blacklisted, 0) = 0
              AND NOT EXISTS (
                SELECT 1 FROM referral_douyin_invites i
                WHERE i.agent_id = a.agent_id AND i.status IN ('pending', 'sent', 'joined')
              )
            ORDER BY a.created_at DESC
            LIMIT ?
            ''',
            [limit]
        ).fetchall())
    created = 0
    for agent in agents:
        queue_douyin_invite(int(agent['agent_id']), remark='批量生成跟进任务')
        created += 1
    return {'queued': created, 'agents': len(agents)}


def update_douyin_invite_status(invite_id: int, status: str, remark: str = '') -> dict[str, Any]:
    ensure_referral_p3_tables()
    if status not in ('pending', 'sent', 'joined', 'rejected', 'skipped'):
        raise ValueError('无效跟进状态')
    sent_at = datetime.now().isoformat(timespec='seconds') if status == 'sent' else None
    with get_connection() as connection:
        row = row_to_dict(connection.execute(
            'SELECT * FROM referral_douyin_invites WHERE invite_id = ?',
            [invite_id]
        ).fetchone())
        if not row:
            raise ValueError('跟进记录不存在')
        connection.execute(
            '''
            UPDATE referral_douyin_invites
            SET status = ?, remark = ?, sent_at = COALESCE(?, sent_at), updated_at = CURRENT_TIMESTAMP
            WHERE invite_id = ?
            ''',
            [status, remark, sent_at, invite_id]
        )
        connection.commit()
        return row_to_dict(connection.execute(
            'SELECT * FROM referral_douyin_invites WHERE invite_id = ?',
            [invite_id]
        ).fetchone())


def get_auto_pay_settings() -> dict[str, Any]:
    from wechat_transfer_service import is_wechat_transfer_ready
    return {
        'enabled': _get_setting('referral_auto_pay_enabled', '0') == '1',
        'ready': is_wechat_transfer_ready(),
    }


def save_auto_pay_settings(enabled: bool) -> dict[str, Any]:
    ensure_referral_p3_tables()
    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP
            ''',
            ['referral_auto_pay_enabled', '1' if enabled else '0']
        )
        connection.commit()
    return get_auto_pay_settings()


def auto_pay_withdrawal(withdrawal_id: int) -> dict[str, Any]:
    from wechat_transfer_service import transfer_to_agent_openid

    ensure_referral_p3_tables()
    with get_connection() as connection:
        withdrawal = row_to_dict(connection.execute(
            '''
            SELECT w.*, a.user_id, a.display_name, u.openid
            FROM referral_withdrawals w
            JOIN referral_agents a ON a.agent_id = w.agent_id
            JOIN users u ON u.user_id = a.user_id
            WHERE w.withdrawal_id = ?
            ''',
            [withdrawal_id]
        ).fetchone())
    if not withdrawal:
        raise ValueError('提现申请不存在')
    if withdrawal.get('status') != 'approved':
        raise ValueError('请先审核通过后再发起微信自动打款')
    if withdrawal.get('pay_method') not in ('wechat', '微信'):
        raise ValueError('仅微信收款方式支持自动打款')
    if withdrawal.get('transfer_bill_no'):
        raise ValueError('该提现已发起过微信转账')

    result = transfer_to_agent_openid(
        openid=withdrawal.get('openid') or '',
        amount_yuan=float(withdrawal.get('amount') or 0),
        withdrawal_id=int(withdrawal_id),
        remark=f'达人佣金提现#{withdrawal_id}',
    )
    bill_no = result.get('out_bill_no') or result.get('out_batch_no') or ''
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE referral_withdrawals
            SET status = 'paid',
                transfer_bill_no = ?,
                transfer_status = ?,
                remark = ?,
                reviewed_at = COALESCE(reviewed_at, CURRENT_TIMESTAMP),
                paid_at = CURRENT_TIMESTAMP
            WHERE withdrawal_id = ?
            ''',
            [bill_no, result.get('status') or 'submitted', result.get('message') or '微信转账已提交', withdrawal_id]
        )
        connection.commit()
        updated = row_to_dict(connection.execute(
            'SELECT * FROM referral_withdrawals WHERE withdrawal_id = ?',
            [withdrawal_id]
        ).fetchone())
    return {'withdrawal': updated, 'transfer': result}


def batch_auto_pay_withdrawals(limit: int = 20) -> dict[str, Any]:
    ensure_referral_p3_tables()
    settings = get_auto_pay_settings()
    if not settings['ready']:
        raise ValueError('微信商家转账未配置，无法自动打款')
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(
            '''
            SELECT withdrawal_id
            FROM referral_withdrawals
            WHERE status = 'approved'
              AND pay_method IN ('wechat', '微信')
              AND IFNULL(transfer_bill_no, '') = ''
            ORDER BY created_at ASC
            LIMIT ?
            ''',
            [max(1, min(int(limit or 20), 50))]
        ).fetchall())
    success = 0
    errors: list[str] = []
    for item in rows:
        try:
            auto_pay_withdrawal(int(item['withdrawal_id']))
            success += 1
        except ValueError as exc:
            errors.append(f'#{item["withdrawal_id"]}: {exc}')
    return {'success': success, 'errors': errors}
