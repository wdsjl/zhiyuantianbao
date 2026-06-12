from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts

REPORT_BEAN_COST = 500

PLAN_BEAN_GRANT: dict[str, int] = {
    'trial': 2000,
    'standard': 12000,
    'premium': 24000,
}

PLAN_CATALOG: dict[str, dict[str, str]] = {
    'trial': {
        'plan_name': '普通卡',
        'description': '一次充值 ¥19.9，到账 2000 星鼎豆',
    },
    'standard': {
        'plan_name': '金卡',
        'description': '起充 ¥99，到账 12000 星鼎豆',
    },
    'premium': {
        'plan_name': '白金卡',
        'description': '起充 ¥168，到账 24000 星鼎豆',
    },
}


def ensure_bean_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_bean_accounts (
              user_id INTEGER PRIMARY KEY,
              balance INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_bean_transactions (
              transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              change_amount INTEGER NOT NULL,
              balance_after INTEGER NOT NULL,
              transaction_type TEXT NOT NULL,
              remark TEXT,
              order_no TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_bean_transactions_user ON user_bean_transactions(user_id, created_at)'
        )
        connection.commit()


def apply_plan_catalog(plan: dict[str, Any] | None) -> dict[str, Any]:
    if not plan:
        return {}
    code = str(plan.get('plan_code') or '')
    meta = PLAN_CATALOG.get(code, {})
    enriched = dict(plan)
    if meta:
        enriched['plan_name'] = meta['plan_name']
        enriched['description'] = meta['description']
    if code in PLAN_BEAN_GRANT:
        enriched['bean_grant'] = PLAN_BEAN_GRANT[code]
    return enriched


def sync_plan_catalog() -> None:
    from membership_service import ensure_membership_tables
    ensure_membership_tables()
    with get_connection() as connection:
        for plan_code, meta in PLAN_CATALOG.items():
            connection.execute(
                '''
                UPDATE membership_plans
                SET plan_name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE plan_code = ?
                ''',
                [meta['plan_name'], meta['description'], plan_code],
            )
        connection.commit()


def get_plan_bean_grant(plan_code: str) -> int:
    return int(PLAN_BEAN_GRANT.get(plan_code) or 0)


def _get_account(connection, user_id: int) -> dict[str, Any]:
    row = row_to_dict(connection.execute(
        'SELECT * FROM user_bean_accounts WHERE user_id = ?',
        [user_id],
    ).fetchone())
    if row:
        return row
    connection.execute(
        'INSERT INTO user_bean_accounts (user_id, balance) VALUES (?, 0)',
        [user_id],
    )
    return {'user_id': user_id, 'balance': 0}


def get_bean_balance(user_id: int) -> dict[str, Any]:
    ensure_bean_tables()
    with get_connection() as connection:
        account = _get_account(connection, user_id)
        connection.commit()
        balance = int(account.get('balance') or 0)
        return {
            'user_id': user_id,
            'balance': balance,
            'report_cost': REPORT_BEAN_COST,
            'can_generate_report': balance >= REPORT_BEAN_COST,
        }


def _append_transaction(
    connection,
    user_id: int,
    change_amount: int,
    balance_after: int,
    transaction_type: str,
    remark: str = '',
    order_no: str = '',
) -> None:
    connection.execute(
        '''
        INSERT INTO user_bean_transactions (
          user_id, change_amount, balance_after, transaction_type, remark, order_no
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''',
        [user_id, change_amount, balance_after, transaction_type, remark, order_no],
    )


def grant_plan_beans(user_id: int, plan_code: str, order_no: str = '', remark: str = '') -> dict[str, Any]:
    amount = get_plan_bean_grant(plan_code)
    if amount <= 0:
        return get_bean_balance(user_id)

    ensure_bean_tables()
    with get_connection() as connection:
        account = _get_account(connection, user_id)
        new_balance = int(account.get('balance') or 0) + amount
        connection.execute(
            '''
            UPDATE user_bean_accounts
            SET balance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''',
            [new_balance, user_id],
        )
        _append_transaction(
            connection,
            user_id,
            amount,
            new_balance,
            'recharge',
            remark or f'充值到账 {amount} 星鼎豆',
            order_no,
        )
        connection.commit()
        return {'user_id': user_id, 'balance': new_balance, 'granted': amount}


def adjust_beans(user_id: int, change_amount: int, remark: str = '') -> dict[str, Any]:
    """后台调整星鼎豆：正数增加，负数扣减。"""
    ensure_bean_tables()
    amount = int(change_amount)
    if amount == 0:
        return get_bean_balance(user_id)

    with get_connection() as connection:
        account = _get_account(connection, user_id)
        new_balance = int(account.get('balance') or 0) + amount
        if new_balance < 0:
            raise ValueError(f'扣减后余额不能为负，当前余额 {account.get("balance") or 0}')
        connection.execute(
            '''
            UPDATE user_bean_accounts
            SET balance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''',
            [new_balance, user_id],
        )
        _append_transaction(
            connection,
            user_id,
            amount,
            new_balance,
            'admin_adjust',
            remark or ('后台增加星鼎豆' if amount > 0 else '后台扣减星鼎豆'),
        )
        connection.commit()
        return {'user_id': user_id, 'balance': new_balance, 'changed': amount}


def set_bean_balance(user_id: int, balance: int, remark: str = '') -> dict[str, Any]:
    """后台直接设置星鼎豆余额。"""
    ensure_bean_tables()
    target = max(0, int(balance))
    with get_connection() as connection:
        account = _get_account(connection, user_id)
        current = int(account.get('balance') or 0)
        delta = target - current
        connection.execute(
            '''
            UPDATE user_bean_accounts
            SET balance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''',
            [target, user_id],
        )
        if delta != 0:
            _append_transaction(
                connection,
                user_id,
                delta,
                target,
                'admin_set',
                remark or f'后台设置余额为 {target} 星鼎豆',
            )
        connection.commit()
        return {'user_id': user_id, 'balance': target, 'changed': delta}


def consume_report_beans(user_id: int, report_title: str = 'AI 报告') -> dict[str, Any]:
    from user_flags_service import is_super_tester

    if is_super_tester(user_id):
        balance_info = get_bean_balance(user_id)
        return {
            **balance_info,
            'consumed': 0,
            'report_title': report_title,
            'super_tester': True,
        }

    ensure_bean_tables()
    cost = REPORT_BEAN_COST
    with get_connection() as connection:
        account = _get_account(connection, user_id)
        balance = int(account.get('balance') or 0)
        if balance < cost:
            raise ValueError(f'星鼎豆不足，当前余额 {balance}，生成报告需要 {cost} 星鼎豆')

        new_balance = balance - cost
        connection.execute(
            '''
            UPDATE user_bean_accounts
            SET balance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''',
            [new_balance, user_id],
        )
        _append_transaction(
            connection,
            user_id,
            -cost,
            new_balance,
            'report_consume',
            f'生成{report_title}消耗 {cost} 星鼎豆',
        )
        connection.commit()
        return {
            'user_id': user_id,
            'balance': new_balance,
            'consumed': cost,
            'report_title': report_title,
        }


def list_bean_transactions(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    ensure_bean_tables()
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(
            '''
            SELECT * FROM user_bean_transactions
            WHERE user_id = ?
            ORDER BY transaction_id DESC
            LIMIT ?
            ''',
            [user_id, limit],
        ).fetchall())
