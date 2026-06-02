import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from html import escape
from typing import Any
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse

from db import get_connection, row_to_dict, rows_to_dicts


SESSION_COOKIE_NAME = 'admin_session'
SESSION_MAX_AGE = 60 * 60 * 8
PASSWORD_ITERATIONS = 260000
SESSION_SECRET = os.getenv('ADMIN_SESSION_SECRET') or 'zhiyuan-admin-session-secret-change-me'

ROLE_LABELS = {
    'super_admin': '超级管理员',
    'admin': '管理员',
    'operator': '运营客服',
    'viewer': '只读查看',
}

ROLE_PERMISSIONS = {
    'super_admin': {'view_admin', 'accounts_manage', 'data_manage', 'membership_manage', 'payment_manage', 'settings_manage'},
    'admin': {'view_admin', 'data_manage', 'membership_manage', 'payment_manage', 'settings_manage'},
    'operator': {'view_admin', 'membership_manage', 'payment_manage'},
    'viewer': {'view_admin'},
}


def ensure_admin_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS admin_accounts (
              admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              display_name TEXT,
              role TEXT NOT NULL DEFAULT 'operator' CHECK(role IN ('super_admin', 'admin', 'operator', 'viewer')),
              is_active INTEGER NOT NULL DEFAULT 1,
              last_login_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute('CREATE INDEX IF NOT EXISTS idx_admin_accounts_username ON admin_accounts(username)')
        connection.commit()


def count_admin_accounts() -> int:
    ensure_admin_tables()
    with get_connection() as connection:
        return int(connection.execute('SELECT COUNT(*) FROM admin_accounts').fetchone()[0])


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PASSWORD_ITERATIONS)
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}'


def verify_password(password: str, password_hash: str) -> bool:
    try:
        method, iterations_text, salt_text, digest_text = password_hash.split('$', 3)
        if method != 'pbkdf2_sha256':
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations_text))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError('密码至少需要 8 位')


def create_admin_account(username: str, password: str, display_name: str = '', role: str = 'operator') -> int:
    ensure_admin_tables()
    username = normalize_username(username)
    if not username:
        raise ValueError('账号不能为空')
    if role not in ROLE_LABELS:
        raise ValueError('角色无效')
    validate_password(password)
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO admin_accounts (username, password_hash, display_name, role)
            VALUES (?, ?, ?, ?)
            ''',
            [username, hash_password(password), display_name.strip(), role]
        )
        connection.commit()
        return int(cursor.lastrowid)


def list_admin_accounts() -> list[dict[str, Any]]:
    ensure_admin_tables()
    with get_connection() as connection:
        return rows_to_dicts(connection.execute('SELECT * FROM admin_accounts ORDER BY admin_id ASC').fetchall())


def get_admin_by_id(admin_id: int) -> dict[str, Any] | None:
    ensure_admin_tables()
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM admin_accounts WHERE admin_id = ?', [admin_id]).fetchone())


def authenticate_admin(username: str, password: str) -> dict[str, Any] | None:
    ensure_admin_tables()
    username = normalize_username(username)
    with get_connection() as connection:
        admin = row_to_dict(connection.execute('SELECT * FROM admin_accounts WHERE username = ?', [username]).fetchone())
        if not admin or not admin.get('is_active'):
            return None
        if not verify_password(password, admin.get('password_hash') or ''):
            return None
        connection.execute('UPDATE admin_accounts SET last_login_at = CURRENT_TIMESTAMP WHERE admin_id = ?', [admin['admin_id']])
        connection.commit()
        admin.pop('password_hash', None)
        return admin


def set_admin_password(admin_id: int, password: str) -> None:
    validate_password(password)
    with get_connection() as connection:
        connection.execute(
            'UPDATE admin_accounts SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE admin_id = ?',
            [hash_password(password), admin_id]
        )
        connection.commit()


def update_admin_profile(admin_id: int, display_name: str, role: str, is_active: bool) -> None:
    if role not in ROLE_LABELS:
        raise ValueError('角色无效')
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE admin_accounts
            SET display_name = ?, role = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE admin_id = ?
            ''',
            [display_name.strip(), role, 1 if is_active else 0, admin_id]
        )
        connection.commit()


def b64_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def unb64_json(value: str) -> dict[str, Any]:
    padded = value + '=' * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode()).decode('utf-8'))


def sign_value(value: str) -> str:
    return hmac.new(SESSION_SECRET.encode('utf-8'), value.encode('utf-8'), hashlib.sha256).hexdigest()


def make_session_cookie(admin: dict[str, Any]) -> str:
    payload = {
        'admin_id': admin['admin_id'],
        'username': admin['username'],
        'role': admin['role'],
        'exp': int(time.time()) + SESSION_MAX_AGE,
    }
    body = b64_json(payload)
    return f'{body}.{sign_value(body)}'


def parse_session_cookie(value: str | None) -> dict[str, Any] | None:
    if not value or '.' not in value:
        return None
    body, signature = value.rsplit('.', 1)
    if not hmac.compare_digest(sign_value(body), signature):
        return None
    try:
        payload = unb64_json(body)
    except Exception:
        return None
    if int(payload.get('exp') or 0) < int(time.time()):
        return None
    admin = get_admin_by_id(int(payload.get('admin_id') or 0))
    if not admin or not admin.get('is_active'):
        return None
    admin.pop('password_hash', None)
    return admin


def current_admin_from_request(request: Request) -> dict[str, Any] | None:
    return parse_session_cookie(request.cookies.get(SESSION_COOKIE_NAME))


def has_permission(admin: dict[str, Any], permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(admin.get('role') or '', set())


def permission_for_admin_request(path: str, method: str) -> str:
    if path.startswith('/admin/accounts'):
        return 'accounts_manage'
    if path.startswith('/admin/llm-settings'):
        return 'settings_manage'
    if path.startswith('/admin/payments'):
        return 'payment_manage'
    if path.startswith('/admin/membership'):
        return 'membership_manage'
    if path.startswith('/admin/import') or path.startswith('/admin/data-sources'):
        return 'data_manage' if method != 'GET' else 'view_admin'
    return 'view_admin'


def simple_admin_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f'''
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>{escape(title)}</title>
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1677ff, #36cfc9); color: #17233d; display: grid; place-items: center; }}
        .box {{ width: min(520px, calc(100vw - 32px)); background: #fff; border-radius: 22px; padding: 30px; box-shadow: 0 24px 80px rgba(16, 24, 40, .24); }}
        h1 {{ margin: 0 0 10px; }}
        p {{ color: #667085; line-height: 1.7; }}
        label {{ display: grid; gap: 8px; margin: 14px 0; color: #475467; font-weight: 700; }}
        input, select {{ height: 44px; border: 1px solid #d0d5dd; border-radius: 12px; padding: 0 12px; }}
        button, .button {{ height: 44px; border: 0; border-radius: 999px; padding: 0 22px; color: white; background: #1677ff; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }}
        .error {{ color: #f04438; background: #fff1f0; padding: 10px 12px; border-radius: 12px; }}
      </style>
    </head>
    <body><main class="box">{body}</main></body>
    </html>
    ''')


def admin_login_page(next_url: str = '/admin', error: str = '') -> HTMLResponse:
    error_html = f'<p class="error">{escape(error)}</p>' if error else ''
    return simple_admin_page('后台登录', f'''
      <h1>后台登录</h1>
      <p>请输入后台管理员账号和密码。</p>
      {error_html}
      <form method="post" action="/admin/login">
        <input type="hidden" name="next_url" value="{escape(next_url)}" />
        <label>账号<input name="username" autocomplete="username" required /></label>
        <label>密码<input name="password" type="password" autocomplete="current-password" required /></label>
        <button type="submit">登录</button>
      </form>
    ''')


def admin_setup_page(error: str = '') -> HTMLResponse:
    error_html = f'<p class="error">{escape(error)}</p>' if error else ''
    return simple_admin_page('初始化后台管理员', f'''
      <h1>初始化后台管理员</h1>
      <p>当前还没有后台账号。请先创建一个超级管理员，后续可在后台开通多个账号并分配权限。</p>
      {error_html}
      <form method="post" action="/admin/setup">
        <label>管理员账号<input name="username" autocomplete="username" required /></label>
        <label>显示名称<input name="display_name" placeholder="例如：管理员" /></label>
        <label>登录密码<input name="password" type="password" autocomplete="new-password" required /></label>
        <label>确认密码<input name="confirm_password" type="password" autocomplete="new-password" required /></label>
        <button type="submit">创建超级管理员</button>
      </form>
    ''')


def forbidden_page(message: str = '当前账号没有权限访问该功能') -> HTMLResponse:
    return simple_admin_page('无权限', f'''
      <h1>无权限</h1>
      <p>{escape(message)}</p>
      <p><a class="button" href="/admin">返回后台首页</a></p>
    ''')


def admin_accounts_page(current_admin: dict[str, Any], message: str = '') -> HTMLResponse:
    accounts = list_admin_accounts()
    role_options = ''.join(f'<option value="{code}">{label}</option>' for code, label in ROLE_LABELS.items())
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    rows = ''
    for account in accounts:
        role_select = ''.join(
            f'<option value="{code}"{" selected" if account.get("role") == code else ""}>{label}</option>'
            for code, label in ROLE_LABELS.items()
        )
        disabled_self = ' disabled' if account['admin_id'] == current_admin['admin_id'] else ''
        active_checked = ' checked' if account.get('is_active') else ''
        rows += f'''
          <tr>
            <td>{account.get('admin_id')}</td>
            <td>{escape(str(account.get('username') or ''))}</td>
            <td>{escape(str(account.get('last_login_at') or '未登录'))}</td>
            <td>
              <form class="toolbar" method="post" action="/admin/accounts/update">
                <input type="hidden" name="admin_id" value="{account.get('admin_id')}" />
                <input name="display_name" value="{escape(str(account.get('display_name') or ''))}" placeholder="显示名称" />
                <select name="role"{disabled_self}>{role_select}</select>
                <label class="inline"><input type="checkbox" name="is_active" value="1"{active_checked}{disabled_self} /> 启用</label>
                <button type="submit"{disabled_self}>保存</button>
              </form>
              <form class="toolbar" method="post" action="/admin/accounts/password">
                <input type="hidden" name="admin_id" value="{account.get('admin_id')}" />
                <input name="password" type="password" placeholder="新密码，至少8位" />
                <button type="submit">重置密码</button>
              </form>
            </td>
          </tr>
        '''
    if not rows:
        rows = '<tr><td colspan="4" class="muted">暂无账号</td></tr>'
    body = f'''
      <div class="card">
        <h2>后台账号管理</h2>
        {message_html}
        <p class="muted">超级管理员可创建多个后台账号，并按角色分配权限。不要把后台账号发给小程序普通用户。</p>
        <form method="post" action="/admin/accounts/create">
          <div class="toolbar">
            <input name="username" placeholder="登录账号" required />
            <input name="display_name" placeholder="显示名称" />
            <input name="password" type="password" placeholder="初始密码，至少8位" required />
            <select name="role">{role_options}</select>
            <button type="submit">创建账号</button>
          </div>
        </form>
      </div>
      <div class="card">
        <h2>账号列表</h2>
        <table><thead><tr><th>ID</th><th>账号</th><th>最近登录</th><th>管理</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
      <div class="card">
        <h2>角色说明</h2>
        <p class="muted">超级管理员：账号管理和全部功能；管理员：除账号管理外全部功能；运营客服：会员和订单处理；只读查看：只能查看基础后台页面。</p>
      </div>
    '''
    from admin_views import page
    return page('后台账号管理', body)


def safe_redirect_target(next_url: str) -> str:
    if not next_url or not next_url.startswith('/') or next_url.startswith('//'):
        return '/admin'
    return next_url


def login_redirect_url(request: Request) -> str:
    path = request.url.path
    query = request.url.query
    target = path + (f'?{query}' if query else '')
    return f'/admin/login?next_url={quote(target)}'
