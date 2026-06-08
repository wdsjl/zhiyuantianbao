from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from membership_service import ensure_membership_tables, grant_membership, revoke_membership


def ensure_payment_tables() -> None:
    ensure_membership_tables()
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS payment_orders (
              order_id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_no TEXT NOT NULL UNIQUE,
              user_id INTEGER NOT NULL,
              plan_code TEXT NOT NULL,
              amount REAL NOT NULL DEFAULT 0,
              pay_method TEXT NOT NULL DEFAULT 'manual',
              pay_status TEXT NOT NULL DEFAULT 'paid' CHECK(pay_status IN ('pending', 'paid', 'refunded', 'cancelled')),
              payer_name TEXT,
              payer_contact TEXT,
              paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              opened_membership_id INTEGER,
              remark TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
              FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE
            )
            '''
        )
        order_columns = [row['name'] for row in connection.execute('PRAGMA table_info(payment_orders)').fetchall()]
        if 'order_type' not in order_columns:
            connection.execute("ALTER TABLE payment_orders ADD COLUMN order_type TEXT NOT NULL DEFAULT 'manual'")
        if 'wx_transaction_id' not in order_columns:
            connection.execute('ALTER TABLE payment_orders ADD COLUMN wx_transaction_id TEXT')
        if 'wx_prepay_id' not in order_columns:
            connection.execute('ALTER TABLE payment_orders ADD COLUMN wx_prepay_id TEXT')
        if 'wx_notify_raw' not in order_columns:
            connection.execute('ALTER TABLE payment_orders ADD COLUMN wx_notify_raw TEXT')
        if 'wx_refund_id' not in order_columns:
            connection.execute('ALTER TABLE payment_orders ADD COLUMN wx_refund_id TEXT')
        if 'wx_refund_no' not in order_columns:
            connection.execute('ALTER TABLE payment_orders ADD COLUMN wx_refund_no TEXT')
        if 'refunded_at' not in order_columns:
            connection.execute('ALTER TABLE payment_orders ADD COLUMN refunded_at TEXT')
        connection.execute('CREATE INDEX IF NOT EXISTS idx_payment_orders_user ON payment_orders(user_id, paid_at)')
        connection.execute('''CREATE TABLE IF NOT EXISTS membership_open_requests (request_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, plan_code TEXT NOT NULL, contact_name TEXT, contact_phone TEXT, message TEXT, request_status TEXT NOT NULL DEFAULT 'pending' CHECK(request_status IN ('pending', 'processed', 'cancelled')), created_order_id INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE, FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE)''')
        columns = [row['name'] for row in connection.execute('PRAGMA table_info(membership_open_requests)').fetchall()]
        if 'request_type' not in columns:
            connection.execute("ALTER TABLE membership_open_requests ADD COLUMN request_type TEXT NOT NULL DEFAULT 'open'")
        connection.execute('CREATE INDEX IF NOT EXISTS idx_open_requests_status ON membership_open_requests(request_status, created_at)')
        connection.execute('''CREATE TABLE IF NOT EXISTS app_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        connection.commit()


def make_order_no(user_id: int) -> str:
    from datetime import datetime
    return f'M{datetime.now().strftime("%Y%m%d%H%M%S")}{user_id}'


def create_pending_order(
    user_id: int,
    plan_code: str,
    amount: float,
    order_type: str = 'open',
    pay_method: str = 'wechat_pay'
) -> tuple[str, int]:
    ensure_payment_tables()
    order_no = make_order_no(user_id)
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO payment_orders (
              order_no, user_id, plan_code, amount, pay_method, pay_status, order_type, paid_at, remark
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, '', ?)
            ''',
            [order_no, user_id, plan_code, float(amount), pay_method, order_type, '']
        )
        connection.commit()
        return order_no, cursor.lastrowid


def get_order_by_order_no(order_no: str) -> dict[str, Any] | None:
    ensure_payment_tables()
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM payment_orders WHERE order_no = ?', [order_no]).fetchone())


def fulfill_wechat_order(order_no: str, transaction_id: str, notify_raw: str = '') -> dict[str, Any]:
    ensure_payment_tables()
    with get_connection() as connection:
        order = row_to_dict(connection.execute('SELECT * FROM payment_orders WHERE order_no = ?', [order_no]).fetchone())
        if not order:
            raise ValueError('订单不存在')
        if order.get('pay_status') == 'paid':
            return order

        membership_id = grant_membership(
            int(order['user_id']),
            order['plan_code'],
            None,
            f'微信支付订单 {order_no}',
            source='wechat_pay'
        )
        connection.execute(
            '''
            UPDATE payment_orders
            SET pay_status = 'paid', pay_method = 'wechat_pay', wx_transaction_id = ?, wx_notify_raw = ?,
                opened_membership_id = ?, paid_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE order_no = ?
            ''',
            [transaction_id, notify_raw, membership_id, order_no]
        )
        connection.commit()
        return row_to_dict(connection.execute('SELECT * FROM payment_orders WHERE order_no = ?', [order_no]).fetchone())


def create_manual_order(data: dict[str, Any]) -> int:
    ensure_payment_tables()
    user_id = int(data['user_id'])
    plan_code = data['plan_code']
    days = int(data['days']) if data.get('days') else None
    remark = data.get('remark') or ''
    order_type = data.get('order_type') or 'manual'
    membership_id = grant_membership(user_id, plan_code, days, remark, source='manual_payment') if data.get('auto_open', True) else None
    order_no = data.get('order_no') or make_order_no(user_id)
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO payment_orders (
              order_no, user_id, plan_code, amount, pay_method, pay_status, order_type, payer_name,
              payer_contact, opened_membership_id, remark
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                order_no, user_id, plan_code, float(data.get('amount') or 0), data.get('pay_method') or 'manual',
                data.get('pay_status') or 'paid', order_type, data.get('payer_name') or '', data.get('payer_contact') or '',
                membership_id, remark
            ]
        )
        connection.commit()
        return cursor.lastrowid


def list_orders(keyword: str = '') -> list[dict[str, Any]]:
    ensure_payment_tables()
    sql = '''
    SELECT po.*, u.phone, u.name AS user_name, s.name AS student_name, s.school_name,
           mp.plan_name
    FROM payment_orders po
    JOIN users u ON u.user_id = po.user_id
    LEFT JOIN students s ON s.user_id = u.user_id
    LEFT JOIN membership_plans mp ON mp.plan_code = po.plan_code
    WHERE 1=1
    '''
    params: list[Any] = []
    if keyword:
        sql += ' AND (po.order_no LIKE ? OR u.phone LIKE ? OR u.name LIKE ? OR s.name LIKE ? OR po.payer_contact LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like, like])
    sql += ' ORDER BY po.paid_at DESC, po.order_id DESC LIMIT 300'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def update_order_status(order_id: int, pay_status: str) -> None:
    ensure_payment_tables()
    with get_connection() as connection:
        connection.execute('UPDATE payment_orders SET pay_status = ?, updated_at = CURRENT_TIMESTAMP WHERE order_id = ?', [pay_status, order_id])
        connection.commit()


def get_order_by_id(order_id: int) -> dict[str, Any] | None:
    ensure_payment_tables()
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM payment_orders WHERE order_id = ?', [order_id]).fetchone())


def is_wechat_pay_order(order: dict[str, Any]) -> bool:
    return str(order.get('pay_method') or '') == 'wechat_pay'


def refund_order(order_id: int, remark: str = '', revoke: bool = True) -> dict[str, Any]:
    ensure_payment_tables()
    with get_connection() as connection:
        order = row_to_dict(connection.execute('SELECT * FROM payment_orders WHERE order_id = ?', [order_id]).fetchone())
        if not order:
            raise ValueError('订单不存在')
        if order.get('pay_status') != 'paid':
            raise ValueError('仅已支付订单可退款')

    refund_note = (remark or '').strip() or '管理员退款'
    wechat_refund: dict[str, Any] | None = None
    if is_wechat_pay_order(order):
        from wechat_pay_service import create_wechat_refund, is_wechat_pay_ready
        if not is_wechat_pay_ready():
            raise ValueError('该订单为微信支付，但商户退款配置未完成，无法原路退回')
        wechat_refund = create_wechat_refund(order, refund_note)

    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE payment_orders
            SET pay_status = 'refunded',
                remark = ?,
                wx_refund_id = ?,
                wx_refund_no = ?,
                refunded_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
            ''',
            [
                refund_note,
                (wechat_refund or {}).get('refund_id') or '',
                (wechat_refund or {}).get('out_refund_no') or '',
                order_id,
            ]
        )
        connection.commit()

    if revoke:
        revoke_membership(int(order['user_id']), f'{refund_note}，会员已撤销')

    return {
        'order_id': order_id,
        'wechat_refunded': bool(wechat_refund),
        'wx_refund_id': (wechat_refund or {}).get('refund_id') or '',
        'message': '已发起微信原路退款，款项将退回用户支付账户' if wechat_refund else '订单已标记退款（线下收款请自行转账）',
    }


def get_order_stats() -> dict[str, Any]:
    ensure_payment_tables()
    with get_connection() as connection:
        total = row_to_dict(connection.execute('SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = ?', ['paid']).fetchone())
        today = row_to_dict(connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = 'paid' AND date(paid_at) = date('now', 'localtime')").fetchone())
    return {'total': total, 'today': today}



def create_open_request(data: dict[str, Any]) -> dict[str, Any]:
    ensure_payment_tables()
    user_id = int(data['user_id'])
    plan_code = data['plan_code']
    request_type = data.get('request_type') or 'open'
    with get_connection() as connection:
        existing = row_to_dict(connection.execute(
            '''
            SELECT mor.*, mp.plan_name, mp.price
            FROM membership_open_requests mor
            LEFT JOIN membership_plans mp ON mp.plan_code = mor.plan_code
            WHERE mor.user_id = ? AND mor.plan_code = ? AND mor.request_status = 'pending'
            ORDER BY mor.created_at DESC
            LIMIT 1
            ''',
            [user_id, plan_code]
        ).fetchone())
        if existing:
            return {'request_id': existing['request_id'], 'duplicate': True, 'request': existing}
        cursor = connection.execute(
            '''
            INSERT INTO membership_open_requests (user_id, plan_code, contact_name, contact_phone, message, request_type)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            [user_id, plan_code, data.get('contact_name') or '', data.get('contact_phone') or '', data.get('message') or '', request_type]
        )
        connection.commit()
        return {'request_id': cursor.lastrowid, 'duplicate': False, 'request': None}


def list_open_requests(status: str = 'pending') -> list[dict[str, Any]]:
    ensure_payment_tables()
    sql = '''
    SELECT mor.*, u.phone, u.name AS user_name, s.name AS student_name, s.school_name, mp.plan_name, mp.price, mp.duration_days
    FROM membership_open_requests mor
    JOIN users u ON u.user_id = mor.user_id
    LEFT JOIN students s ON s.user_id = u.user_id
    LEFT JOIN membership_plans mp ON mp.plan_code = mor.plan_code
    WHERE 1=1
    '''
    params: list[Any] = []
    if status:
        sql += ' AND mor.request_status = ?'
        params.append(status)
    sql += ' ORDER BY mor.created_at DESC LIMIT 200'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def mark_open_request_processed(request_id: int, order_id: int) -> None:
    ensure_payment_tables()
    with get_connection() as connection:
        connection.execute(
            'UPDATE membership_open_requests SET request_status = ?, created_order_id = ?, updated_at = CURRENT_TIMESTAMP WHERE request_id = ?',
            ['processed', order_id, request_id]
        )
        connection.commit()


def cancel_open_request(request_id: int) -> None:
    ensure_payment_tables()
    with get_connection() as connection:
        connection.execute('UPDATE membership_open_requests SET request_status = ?, updated_at = CURRENT_TIMESTAMP WHERE request_id = ?', ['cancelled', request_id])
        connection.commit()


def create_order_from_request(request_id: int, amount: float, pay_method: str = 'manual', remark: str = '') -> int:
    ensure_payment_tables()
    with get_connection() as connection:
        request = row_to_dict(connection.execute('SELECT * FROM membership_open_requests WHERE request_id = ?', [request_id]).fetchone())
    if not request:
        raise ValueError('开通申请不存在')
    order_id = create_manual_order({
        'user_id': request['user_id'],
        'plan_code': request['plan_code'],
        'amount': amount,
        'pay_method': pay_method,
        'payer_name': request.get('contact_name') or '',
        'payer_contact': request.get('contact_phone') or '',
        'remark': remark or request.get('message') or '',
        'order_type': request.get('request_type') or 'open',
        'auto_open': True
    })
    mark_open_request_processed(request_id, order_id)
    return order_id



def list_user_open_requests(user_id: int) -> list[dict[str, Any]]:
    ensure_payment_tables()
    sql = '''
    SELECT mor.*, mp.plan_name, mp.price, mp.duration_days
    FROM membership_open_requests mor
    LEFT JOIN membership_plans mp ON mp.plan_code = mor.plan_code
    WHERE mor.user_id = ?
    ORDER BY mor.created_at DESC
    LIMIT 50
    '''
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, [user_id]).fetchall())


def list_user_orders(user_id: int) -> list[dict[str, Any]]:
    ensure_payment_tables()
    sql = '''
    SELECT po.*, mp.plan_name, mp.duration_days
    FROM payment_orders po
    LEFT JOIN membership_plans mp ON mp.plan_code = po.plan_code
    WHERE po.user_id = ?
    ORDER BY po.paid_at DESC, po.order_id DESC
    LIMIT 50
    '''
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, [user_id]).fetchall())



def get_support_contact() -> dict[str, str]:
    ensure_payment_tables()
    defaults = {
        'support_wechat': '',
        'support_phone': '',
        'support_note': '提交开通申请后，请联系客服并备注手机号和套餐名称。客服确认收款后会为您开通会员。'
    }
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(
            "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('support_wechat', 'support_phone', 'support_note')"
        ).fetchall())
    for row in rows:
        defaults[row['setting_key']] = row.get('setting_value') or ''
    return defaults


def save_support_contact(data: dict[str, Any]) -> None:
    ensure_payment_tables()
    values = {
        'support_wechat': data.get('support_wechat') or '',
        'support_phone': data.get('support_phone') or '',
        'support_note': data.get('support_note') or ''
    }
    with get_connection() as connection:
        for key, value in values.items():
            connection.execute(
                '''INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP''',
                [key, value]
            )
        connection.commit()



def export_orders_csv(keyword: str = '') -> str:
    import csv
    import io
    orders = list_orders(keyword)
    type_map = {'open': '新开通', 'renew': '续费', 'manual': '手动调整'}
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    status_map = {'pending': '待支付', 'paid': '已支付', 'refunded': '已退款', 'cancelled': '已取消'}
    method_map = {'wechat_pay': '微信支付', 'wechat_private': '微信私聊', 'wechat_work': '企业微信', 'manual': '手动登记', 'cash': '现金'}
    writer.writerow(['订单ID', '订单号', '用户ID', '手机号', '姓名', '学校', '套餐', '订单类型', '金额', '支付方式', '支付状态', '联系方式', '支付时间', '退款时间', '微信退款单号', '备注'])
    for order in orders:
        writer.writerow([
            order.get('order_id', ''),
            order.get('order_no', ''),
            order.get('user_id', ''),
            order.get('phone', ''),
            order.get('student_name') or order.get('user_name') or '',
            order.get('school_name', ''),
            order.get('plan_name') or order.get('plan_code') or '',
            type_map.get(order.get('order_type'), order.get('order_type') or ''),
            order.get('amount', 0),
            method_map.get(order.get('pay_method'), order.get('pay_method') or ''),
            status_map.get(order.get('pay_status'), order.get('pay_status') or ''),
            order.get('payer_contact', ''),
            order.get('paid_at', ''),
            order.get('refunded_at', ''),
            order.get('wx_refund_no', ''),
            order.get('remark', '')
        ])
    return output.getvalue()



def export_open_requests_csv(status: str = '') -> str:
    import csv
    import io
    requests = list_open_requests(status)
    type_map = {'open': '开通', 'renew': '续费'}
    status_map = {'pending': '待处理', 'processed': '已处理', 'cancelled': '已取消'}
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['申请ID', '用户ID', '手机号', '姓名', '学校', '套餐', '申请类型', '申请状态', '应收金额', '联系人', '联系方式', '留言', '申请时间', '处理订单ID'])
    for item in requests:
        writer.writerow([
            item.get('request_id', ''),
            item.get('user_id', ''),
            item.get('phone', ''),
            item.get('student_name') or item.get('user_name') or '',
            item.get('school_name', ''),
            item.get('plan_name') or item.get('plan_code') or '',
            type_map.get(item.get('request_type'), item.get('request_type') or ''),
            status_map.get(item.get('request_status'), item.get('request_status') or ''),
            item.get('price', 0),
            item.get('contact_name', ''),
            item.get('contact_phone', ''),
            item.get('message', ''),
            item.get('created_at', ''),
            item.get('created_order_id', '')
        ])
    return output.getvalue()
