from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from membership_service import ensure_membership_tables, expire_overdue_memberships
from payment_service import ensure_payment_tables


def get_dashboard_stats() -> dict[str, Any]:
    ensure_membership_tables()
    ensure_payment_tables()
    expired_count = expire_overdue_memberships()
    with get_connection() as connection:
        pending_requests = row_to_dict(connection.execute("SELECT COUNT(*) AS count FROM membership_open_requests WHERE request_status = 'pending'").fetchone())
        today_orders = row_to_dict(connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = 'paid' AND date(paid_at) = date('now', 'localtime')").fetchone())
        total_orders = row_to_dict(connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = 'paid'").fetchone())
        today_open_orders = row_to_dict(connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = 'paid' AND order_type = 'open' AND date(paid_at) = date('now', 'localtime')").fetchone())
        today_renew_orders = row_to_dict(connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = 'paid' AND order_type = 'renew' AND date(paid_at) = date('now', 'localtime')").fetchone())
        total_open_orders = row_to_dict(connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = 'paid' AND order_type = 'open'").fetchone())
        total_renew_orders = row_to_dict(connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM payment_orders WHERE pay_status = 'paid' AND order_type = 'renew'").fetchone())
        active_members = row_to_dict(connection.execute("SELECT COUNT(*) AS count FROM user_memberships WHERE status = 'active' AND (expires_at IS NULL OR expires_at > datetime('now', 'localtime'))").fetchone())
        expiring_members = row_to_dict(connection.execute("SELECT COUNT(*) AS count FROM user_memberships WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at BETWEEN datetime('now', 'localtime') AND datetime('now', '+7 days', 'localtime')").fetchone())
        ai_today = row_to_dict(connection.execute("SELECT COALESCE(SUM(used_count), 0) AS count FROM user_permission_usage WHERE permission_code = 'ai_plan_explain' AND period_key = 'day:' || date('now', 'localtime')").fetchone())
        today_new_requests = row_to_dict(connection.execute("SELECT COUNT(*) AS count FROM membership_open_requests WHERE date(created_at) = date('now', 'localtime')").fetchone())
        today_processed_requests = row_to_dict(connection.execute("SELECT COUNT(*) AS count FROM membership_open_requests WHERE request_status = 'processed' AND date(updated_at) = date('now', 'localtime')").fetchone())
        request_conversion_total = row_to_dict(connection.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN request_status = 'processed' THEN 1 ELSE 0 END) AS processed FROM membership_open_requests").fetchone())
        request_conversion_open = row_to_dict(connection.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN request_status = 'processed' THEN 1 ELSE 0 END) AS processed FROM membership_open_requests WHERE request_type = 'open'").fetchone())
        request_conversion_renew = row_to_dict(connection.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN request_status = 'processed' THEN 1 ELSE 0 END) AS processed FROM membership_open_requests WHERE request_type = 'renew'").fetchone())
        recent_requests = rows_to_dicts(connection.execute(
            '''
            SELECT mor.request_id, mor.user_id, mor.plan_code, mor.created_at, mor.contact_phone,
                   u.phone, s.name AS student_name, mp.plan_name, mp.price
            FROM membership_open_requests mor
            JOIN users u ON u.user_id = mor.user_id
            LEFT JOIN students s ON s.user_id = u.user_id
            LEFT JOIN membership_plans mp ON mp.plan_code = mor.plan_code
            WHERE mor.request_status = 'pending'
            ORDER BY mor.created_at DESC
            LIMIT 8
            '''
        ).fetchall())
        recent_orders = rows_to_dicts(connection.execute(
            '''
            SELECT po.order_id, po.order_no, po.amount, po.pay_method, po.paid_at,
                   u.phone, s.name AS student_name, mp.plan_name
            FROM payment_orders po
            JOIN users u ON u.user_id = po.user_id
            LEFT JOIN students s ON s.user_id = u.user_id
            LEFT JOIN membership_plans mp ON mp.plan_code = po.plan_code
            WHERE po.pay_status = 'paid'
            ORDER BY po.paid_at DESC, po.order_id DESC
            LIMIT 8
            '''
        ).fetchall())
    return {
        'pending_requests': pending_requests,
        'today_orders': today_orders,
        'total_orders': total_orders,
        'today_open_orders': today_open_orders,
        'today_renew_orders': today_renew_orders,
        'total_open_orders': total_open_orders,
        'total_renew_orders': total_renew_orders,
        'active_members': active_members,
        'expiring_members': expiring_members,
        'ai_today': ai_today,
        'today_new_requests': today_new_requests,
        'today_processed_requests': today_processed_requests,
        'request_conversion_total': request_conversion_total,
        'request_conversion_open': request_conversion_open,
        'request_conversion_renew': request_conversion_renew,
        'expired_count': {'count': expired_count},
        'recent_requests': recent_requests,
        'recent_orders': recent_orders
    }
