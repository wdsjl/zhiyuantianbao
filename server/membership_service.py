from datetime import datetime, timedelta
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts

DEFAULT_PLANS = [
    ('free', '免费版', 0, 0, 1, '基础永久免费，引流体验'),
    ('trial', '普通卡', 19.9, 30, 2, '一次充值 ¥19.9，到账 2000 星鼎豆'),
    ('standard', '金卡', 99, 365, 3, '起充 ¥99，到账 12000 星鼎豆'),
    ('premium', '白金卡', 168, 365, 4, '起充 ¥168，到账 24000 星鼎豆'),
]

DEFAULT_PERMISSIONS = [
    ('personality_basic', '基础性格测评报告', '测评'), ('personality_deep', '深度测评报告', '测评'),
    ('school_basic', '院校/专业基础查询', '查询'), ('score_recent_2y', '近2年分数线', '查询'),
    ('score_full_history', '完整历年分数线和位次', '查询'), ('manual_simulation', '手动志愿模拟', '志愿'),
    ('smart_recommend', '智能志愿推荐', '志愿'), ('risk_inspect', '志愿风险检测', '志愿'),
    ('ai_plan_explain', 'AI 志愿方案解读', 'AI'), ('draft_save', '志愿草稿保存', '志愿'),
    ('pdf_export', 'PDF 志愿表导出', '导出'), ('school_compare', '院校对比', '查询'),
    ('major_deep_guide', '专业避坑和就业方向', '专业'), ('same_rank_reference', '同分段往届参考', '高级'),
    ('premium_school_detail', '院校深度对比', '高级'), ('region_career_plan', '地域就业规划推荐', '专业'),
    ('volunteer_template', '志愿模板包', '增值'), ('question_channel', '专属答疑通道', '服务'),
    ('recruit_notice', '招生计划/征集志愿提醒', '提醒'),
]

DEFAULT_PLAN_PERMISSIONS = {
    'free': {'personality_basic': -1, 'school_basic': -1, 'score_recent_2y': -1, 'manual_simulation': -1},
    'trial': {'personality_basic': -1, 'personality_deep': -1, 'school_basic': -1, 'score_recent_2y': -1, 'score_full_history': -1, 'manual_simulation': -1, 'school_compare': 10, 'smart_recommend': 3, 'risk_inspect': 3, 'ai_plan_explain': 3, 'draft_save': 3, 'pdf_export': -1},
    'standard': {'personality_basic': -1, 'personality_deep': -1, 'school_basic': -1, 'score_recent_2y': -1, 'score_full_history': -1, 'manual_simulation': -1, 'school_compare': -1, 'smart_recommend': -1, 'risk_inspect': -1, 'ai_plan_explain': 5, 'draft_save': -1, 'pdf_export': -1, 'major_deep_guide': -1, 'volunteer_template': -1},
    'premium': {'personality_basic': -1, 'personality_deep': -1, 'school_basic': -1, 'score_recent_2y': -1, 'score_full_history': -1, 'manual_simulation': -1, 'school_compare': -1, 'smart_recommend': -1, 'risk_inspect': -1, 'ai_plan_explain': 20, 'draft_save': -1, 'pdf_export': -1, 'major_deep_guide': -1, 'same_rank_reference': -1, 'premium_school_detail': -1, 'region_career_plan': -1, 'volunteer_template': -1, 'question_channel': -1, 'recruit_notice': -1},
}


def ensure_membership_tables() -> None:
    with get_connection() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS membership_plans (plan_code TEXT PRIMARY KEY, plan_name TEXT NOT NULL, price REAL NOT NULL DEFAULT 0, duration_days INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0, description TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS membership_permissions (permission_code TEXT PRIMARY KEY, permission_name TEXT NOT NULL, category TEXT, description TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS membership_plan_permissions (plan_code TEXT NOT NULL, permission_code TEXT NOT NULL, is_enabled INTEGER NOT NULL DEFAULT 0, limit_value INTEGER NOT NULL DEFAULT 0, remark TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (plan_code, permission_code), FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE, FOREIGN KEY (permission_code) REFERENCES membership_permissions(permission_code) ON DELETE CASCADE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_memberships (user_membership_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, plan_code TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'expired', 'disabled')), starts_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, expires_at TEXT, source TEXT, remark TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE, FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE)''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_memberships_user ON user_memberships(user_id, status, expires_at)')
        c.execute('''CREATE TABLE IF NOT EXISTS user_permission_usage (usage_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, permission_code TEXT NOT NULL, plan_code TEXT NOT NULL, user_membership_id INTEGER, period_key TEXT NOT NULL, used_count INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, permission_code, period_key), FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE)''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_permission_usage_user ON user_permission_usage(user_id, permission_code, period_key)')
        c.commit()
    seed_membership_defaults()


def seed_membership_defaults() -> None:
    with get_connection() as c:
        for plan in DEFAULT_PLANS:
            c.execute('INSERT OR IGNORE INTO membership_plans (plan_code, plan_name, price, duration_days, sort_order, description) VALUES (?, ?, ?, ?, ?, ?)', plan)
        for plan in DEFAULT_PLANS:
            c.execute(
                '''
                UPDATE membership_plans
                SET plan_name = ?, description = ?, price = ?, duration_days = ?, sort_order = ?, updated_at = CURRENT_TIMESTAMP
                WHERE plan_code = ?
                ''',
                [plan[1], plan[5], plan[2], plan[3], plan[4], plan[0]],
            )
        for code, name, category in DEFAULT_PERMISSIONS:
            c.execute('INSERT OR IGNORE INTO membership_permissions (permission_code, permission_name, category) VALUES (?, ?, ?)', [code, name, category])
        for plan_code, permissions in DEFAULT_PLAN_PERMISSIONS.items():
            for permission_code, limit_value in permissions.items():
                c.execute('INSERT OR IGNORE INTO membership_plan_permissions (plan_code, permission_code, is_enabled, limit_value) VALUES (?, ?, ?, ?)', [plan_code, permission_code, 1, limit_value])
        sync_default_plan_permission_limits(c)
        c.commit()


def sync_default_plan_permission_limits(connection) -> None:
    """将代码中的默认权限次数同步到数据库（星鼎豆体系下 PDF 导出等已调整的项）。"""
    for plan_code, permissions in DEFAULT_PLAN_PERMISSIONS.items():
        for permission_code, limit_value in permissions.items():
            connection.execute(
                '''
                UPDATE membership_plan_permissions
                SET limit_value = ?, is_enabled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE plan_code = ? AND permission_code = ?
                ''',
                [limit_value, plan_code, permission_code],
            )


def list_plans() -> list[dict[str, Any]]:
    ensure_membership_tables()
    with get_connection() as c:
        return rows_to_dicts(c.execute('SELECT * FROM membership_plans ORDER BY sort_order ASC, price ASC').fetchall())


def list_permissions() -> list[dict[str, Any]]:
    ensure_membership_tables()
    with get_connection() as c:
        return rows_to_dicts(c.execute('SELECT * FROM membership_permissions ORDER BY category ASC, permission_code ASC').fetchall())


def get_plan_permission_map() -> dict[str, dict[str, dict[str, Any]]]:
    ensure_membership_tables()
    with get_connection() as c:
        rows = rows_to_dicts(c.execute('SELECT * FROM membership_plan_permissions').fetchall())
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row['plan_code'], {})[row['permission_code']] = row
    return result


def save_plan(data: dict[str, Any]) -> None:
    ensure_membership_tables()
    with get_connection() as c:
        c.execute('''INSERT INTO membership_plans (plan_code, plan_name, price, duration_days, is_active, sort_order, description) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(plan_code) DO UPDATE SET plan_name = excluded.plan_name, price = excluded.price, duration_days = excluded.duration_days, is_active = excluded.is_active, sort_order = excluded.sort_order, description = excluded.description, updated_at = CURRENT_TIMESTAMP''', [data['plan_code'], data['plan_name'], float(data.get('price') or 0), int(data.get('duration_days') or 0), 1 if data.get('is_active') else 0, int(data.get('sort_order') or 0), data.get('description') or ''])
        c.commit()


def save_plan_permission(plan_code: str, permission_code: str, is_enabled: bool, limit_value: int = 0, remark: str = '') -> None:
    ensure_membership_tables()
    with get_connection() as c:
        c.execute('''INSERT INTO membership_plan_permissions (plan_code, permission_code, is_enabled, limit_value, remark) VALUES (?, ?, ?, ?, ?) ON CONFLICT(plan_code, permission_code) DO UPDATE SET is_enabled = excluded.is_enabled, limit_value = excluded.limit_value, remark = excluded.remark, updated_at = CURRENT_TIMESTAMP''', [plan_code, permission_code, 1 if is_enabled else 0, int(limit_value or 0), remark])
        c.commit()


def search_users(keyword: str = '') -> list[dict[str, Any]]:
    ensure_membership_tables()
    from user_flags_service import ensure_user_flags
    from bean_service import ensure_bean_tables
    ensure_user_flags()
    ensure_bean_tables()
    sql = '''
    SELECT u.user_id, u.phone, u.role, u.name, u.created_at, u.is_super_tester,
           COALESCE(uba.balance, 0) AS bean_balance,
           s.student_id, s.name AS student_name, s.school_name, s.score, s.rank,
           um.plan_code, mp.plan_name, um.status AS membership_status, um.expires_at
    FROM users u
    LEFT JOIN user_bean_accounts uba ON uba.user_id = u.user_id
    LEFT JOIN students s ON s.user_id = u.user_id
    LEFT JOIN user_memberships um ON um.user_membership_id = (
      SELECT user_membership_id FROM user_memberships
      WHERE user_id = u.user_id AND status = 'active'
      ORDER BY datetime(COALESCE(expires_at, '2999-12-31')) DESC, user_membership_id DESC
      LIMIT 1
    )
    LEFT JOIN membership_plans mp ON mp.plan_code = um.plan_code
    WHERE 1=1
    '''
    params: list[Any] = []
    if keyword:
        sql += ' AND (u.phone LIKE ? OR u.name LIKE ? OR s.name LIKE ? OR s.school_name LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY u.updated_at DESC LIMIT 200'
    with get_connection() as c:
        return rows_to_dicts(c.execute(sql, params).fetchall())


def grant_membership(user_id: int, plan_code: str, days: int | None = None, remark: str = '', source: str = 'admin') -> int:
    ensure_membership_tables()
    with get_connection() as c:
        plan = row_to_dict(c.execute('SELECT * FROM membership_plans WHERE plan_code = ?', [plan_code]).fetchone())
        if not plan:
            raise ValueError('套餐不存在')
        duration_days = int(days if days is not None else plan.get('duration_days') or 0)
        now = datetime.now()
        active = row_to_dict(c.execute(
            '''SELECT * FROM user_memberships WHERE user_id = ? AND status = 'active' ORDER BY datetime(COALESCE(expires_at, '2999-12-31')) DESC, user_membership_id DESC LIMIT 1''',
            [user_id]
        ).fetchone())
        starts_at = now
        base_at = now
        if active and active.get('plan_code') == plan_code and active.get('expires_at'):
            try:
                current_expires_at = datetime.strptime(active['expires_at'], '%Y-%m-%d %H:%M:%S')
                if current_expires_at > now:
                    base_at = current_expires_at
                    starts_at = current_expires_at
            except ValueError:
                base_at = now
        expires_at = None if duration_days <= 0 else (base_at + timedelta(days=duration_days)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute('UPDATE user_memberships SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND status = ?', ['disabled', user_id, 'active'])
        cursor = c.execute('INSERT INTO user_memberships (user_id, plan_code, status, starts_at, expires_at, source, remark) VALUES (?, ?, ?, ?, ?, ?, ?)', [user_id, plan_code, 'active', starts_at.strftime('%Y-%m-%d %H:%M:%S'), expires_at, source, remark])
        c.commit()
        return cursor.lastrowid


def get_active_membership(user_id: int) -> dict[str, Any] | None:
    ensure_membership_tables()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_connection() as c:
        return row_to_dict(c.execute('''SELECT um.*, mp.plan_name, mp.price, mp.duration_days FROM user_memberships um JOIN membership_plans mp ON mp.plan_code = um.plan_code WHERE um.user_id = ? AND um.status = 'active' AND (um.expires_at IS NULL OR um.expires_at >= ?) ORDER BY datetime(COALESCE(um.expires_at, '2999-12-31')) DESC, um.user_membership_id DESC LIMIT 1''', [user_id, now]).fetchone())



def get_latest_membership(user_id: int) -> dict[str, Any] | None:
    ensure_membership_tables()
    with get_connection() as c:
        return row_to_dict(c.execute(
            '''SELECT um.*, mp.plan_name, mp.price, mp.duration_days FROM user_memberships um JOIN membership_plans mp ON mp.plan_code = um.plan_code WHERE um.user_id = ? ORDER BY um.user_membership_id DESC LIMIT 1''',
            [user_id]
        ).fetchone())


def get_user_entitlements(user_id: int | None = None) -> dict[str, Any]:
    ensure_membership_tables()
    expire_overdue_memberships()
    membership = get_active_membership(user_id) if user_id else None
    latest_membership = get_latest_membership(user_id) if user_id else None
    plan_code = membership['plan_code'] if membership else 'free'
    with get_connection() as c:
        plan = row_to_dict(c.execute('SELECT * FROM membership_plans WHERE plan_code = ?', [plan_code]).fetchone())
        rows = rows_to_dicts(c.execute('''SELECT mp.permission_code, mp.permission_name, mp.category, p.is_enabled, p.limit_value, p.remark FROM membership_permissions mp LEFT JOIN membership_plan_permissions p ON p.permission_code = mp.permission_code AND p.plan_code = ? ORDER BY mp.category ASC, mp.permission_code ASC''', [plan_code]).fetchall())
    permissions = {}
    for row in rows:
        limit_value = row.get('limit_value') or 0
        usage = {'used': 0, 'remaining': -1 if int(limit_value) < 0 else int(limit_value), 'period_key': ''}
        if user_id and bool(row.get('is_enabled')) and int(limit_value) >= 0:
            usage_row = get_permission_usage(user_id, row['permission_code'], plan_code, membership)
            usage['used'] = usage_row['used']
            usage['remaining'] = max(int(limit_value) - int(usage_row['used']), 0)
            usage['period_key'] = usage_row['period_key']
        permissions[row['permission_code']] = {
            'enabled': bool(row.get('is_enabled')),
            'limit': limit_value,
            'name': row.get('permission_name'),
            'category': row.get('category'),
            'remark': row.get('remark'),
            'usage': usage
        }
    from bean_service import apply_plan_catalog
    plan = apply_plan_catalog(plan)
    if membership and plan.get('plan_name'):
        membership = {**membership, 'plan_name': plan['plan_name']}
    if latest_membership and plan.get('plan_name'):
        latest_membership = {**latest_membership, 'plan_name': plan['plan_name']}
    from user_flags_service import is_super_tester
    return {
        'plan': plan,
        'membership': membership,
        'latest_membership': latest_membership,
        'permissions': permissions,
        'super_tester': bool(user_id and is_super_tester(user_id)),
    }



def get_usage_period_key(plan_code: str, permission_code: str, membership: dict[str, Any] | None) -> str:
    if permission_code == 'ai_plan_explain' and plan_code in ['standard', 'premium']:
        return f'day:{datetime.now().strftime("%Y-%m-%d")}'
    if membership:
        return f'membership:{membership.get("user_membership_id")}'
    return 'free'


def get_permission_usage(user_id: int, permission_code: str, plan_code: str, membership: dict[str, Any] | None) -> dict[str, Any]:
    ensure_membership_tables()
    period_key = get_usage_period_key(plan_code, permission_code, membership)
    with get_connection() as c:
        row = row_to_dict(c.execute('SELECT * FROM user_permission_usage WHERE user_id = ? AND permission_code = ? AND period_key = ?', [user_id, permission_code, period_key]).fetchone())
    return {'period_key': period_key, 'used': row.get('used_count', 0) if row else 0}


def check_permission(user_id: int | None, permission_code: str) -> dict[str, Any]:
    from user_flags_service import is_super_tester
    if user_id and is_super_tester(user_id):
        return {
            'allowed': True,
            'remaining': -1,
            'used': 0,
            'limit': -1,
            'super_tester': True,
            'message': '超级测试账号，功能不限次',
        }
    entitlements = get_user_entitlements(user_id)
    plan = entitlements.get('plan') or {'plan_code': 'free', 'plan_name': '免费版'}
    membership = entitlements.get('membership')
    permission = entitlements.get('permissions', {}).get(permission_code)
    if not permission or not permission.get('enabled'):
        return {'allowed': False, 'reason': 'not_enabled', 'message': '当前套餐未开通该功能', 'permission': permission, 'plan': plan}
    limit_value = int(permission.get('limit') or 0)
    if limit_value < 0 or not user_id:
        return {'allowed': True, 'remaining': -1, 'used': 0, 'limit': limit_value, 'permission': permission, 'plan': plan}
    usage = get_permission_usage(user_id, permission_code, plan['plan_code'], membership)
    remaining = max(limit_value - int(usage['used']), 0)
    return {
        'allowed': remaining > 0,
        'reason': '' if remaining > 0 else 'limit_exceeded',
        'message': '该功能次数已用完，请升级或联系管理员调整套餐',
        'remaining': remaining,
        'used': usage['used'],
        'limit': limit_value,
        'period_key': usage['period_key'],
        'permission': permission,
        'plan': plan
    }


def consume_permission(user_id: int, permission_code: str) -> dict[str, Any]:
    check = check_permission(user_id, permission_code)
    if not check.get('allowed'):
        return check
    limit_value = int(check.get('limit') or 0)
    if limit_value < 0:
        return {**check, 'consumed': False}
    membership = get_active_membership(user_id)
    plan_code = (check.get('plan') or {}).get('plan_code') or 'free'
    period_key = get_usage_period_key(plan_code, permission_code, membership)
    with get_connection() as c:
        c.execute(
            '''INSERT INTO user_permission_usage (user_id, permission_code, plan_code, user_membership_id, period_key, used_count) VALUES (?, ?, ?, ?, ?, 1) ON CONFLICT(user_id, permission_code, period_key) DO UPDATE SET used_count = used_count + 1, updated_at = CURRENT_TIMESTAMP''',
            [user_id, permission_code, plan_code, membership.get('user_membership_id') if membership else None, period_key]
        )
        c.commit()
    return {**check_permission(user_id, permission_code), 'consumed': True}



def list_permission_usage(keyword: str = '') -> list[dict[str, Any]]:
    ensure_membership_tables()
    sql = '''
    SELECT upu.usage_id, upu.user_id, u.phone, u.name AS user_name, s.name AS student_name, s.school_name,
           upu.permission_code, mp.permission_name, upu.plan_code, pl.plan_name,
           upu.period_key, upu.used_count, upu.updated_at, upu.created_at
    FROM user_permission_usage upu
    JOIN users u ON u.user_id = upu.user_id
    LEFT JOIN students s ON s.user_id = u.user_id
    LEFT JOIN membership_permissions mp ON mp.permission_code = upu.permission_code
    LEFT JOIN membership_plans pl ON pl.plan_code = upu.plan_code
    WHERE 1=1
    '''
    params: list[Any] = []
    if keyword:
        sql += ' AND (u.phone LIKE ? OR u.name LIKE ? OR s.name LIKE ? OR s.school_name LIKE ? OR upu.permission_code LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like, like])
    sql += ' ORDER BY upu.updated_at DESC LIMIT 300'
    with get_connection() as c:
        return rows_to_dicts(c.execute(sql, params).fetchall())


def reset_permission_usage(usage_id: int) -> None:
    ensure_membership_tables()
    with get_connection() as c:
        c.execute('UPDATE user_permission_usage SET used_count = 0, updated_at = CURRENT_TIMESTAMP WHERE usage_id = ?', [usage_id])
        c.commit()


def delete_permission_usage(usage_id: int) -> None:
    ensure_membership_tables()
    with get_connection() as c:
        c.execute('DELETE FROM user_permission_usage WHERE usage_id = ?', [usage_id])
        c.commit()



def list_expiring_members(days: int = 7) -> list[dict[str, Any]]:
    ensure_membership_tables()
    with get_connection() as c:
        return rows_to_dicts(c.execute(
            '''
            SELECT um.user_membership_id, um.user_id, um.plan_code, um.starts_at, um.expires_at, um.remark,
                   u.phone, u.name AS user_name, s.name AS student_name, s.school_name,
                   mp.plan_name, mp.price, mp.duration_days
            FROM user_memberships um
            JOIN users u ON u.user_id = um.user_id
            LEFT JOIN students s ON s.user_id = u.user_id
            LEFT JOIN membership_plans mp ON mp.plan_code = um.plan_code
            WHERE um.status = 'active'
              AND um.expires_at IS NOT NULL
              AND um.expires_at BETWEEN datetime('now', 'localtime') AND datetime('now', ? || ' days', 'localtime')
            ORDER BY um.expires_at ASC
            LIMIT 200
            ''',
            [days]
        ).fetchall())



def revoke_membership(user_id: int, remark: str = '') -> None:
    ensure_membership_tables()
    with get_connection() as c:
        c.execute(
            "UPDATE user_memberships SET status = 'disabled', remark = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND status = 'active'",
            [remark or '管理员撤销', user_id]
        )
        c.commit()


def adjust_permission_usage(usage_id: int, delta: int) -> None:
    ensure_membership_tables()
    with get_connection() as c:
        row = row_to_dict(c.execute('SELECT used_count FROM user_permission_usage WHERE usage_id = ?', [usage_id]).fetchone())
        if not row:
            raise ValueError('次数记录不存在')
        new_count = max(int(row['used_count']) + int(delta), 0)
        c.execute(
            'UPDATE user_permission_usage SET used_count = ?, updated_at = CURRENT_TIMESTAMP WHERE usage_id = ?',
            [new_count, usage_id]
        )
        c.commit()


def export_permission_usage_csv(keyword: str = '') -> str:
    import csv
    import io
    rows = list_permission_usage(keyword)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', '用户ID', '手机号', '姓名', '学校', '套餐', '功能', '周期', '已用', '更新时间'])
    for row in rows:
        writer.writerow([
            row.get('usage_id'), row.get('user_id'), row.get('phone'),
            row.get('student_name') or row.get('user_name'), row.get('school_name'),
            row.get('plan_name') or row.get('plan_code'),
            row.get('permission_name') or row.get('permission_code'),
            row.get('period_key'), row.get('used_count'), row.get('updated_at')
        ])
    return output.getvalue()


def expire_overdue_memberships() -> int:
    ensure_membership_tables()
    with get_connection() as c:
        cursor = c.execute(
            '''
            UPDATE user_memberships
            SET status = 'expired', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'active'
              AND expires_at IS NOT NULL
              AND datetime(expires_at) <= datetime('now', 'localtime')
            '''
        )
        c.commit()
        return cursor.rowcount or 0
