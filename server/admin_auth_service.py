import hashlib
import hmac
import os
import secrets
import time
from typing import Any

from db import get_connection, row_to_dict

ADMIN_SESSION_COOKIE = 'admin_session'
SESSION_MAX_AGE = 60 * 60 * 24 * 7
DEFAULT_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
DEFAULT_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
SESSION_SECRET = os.environ.get('ADMIN_SESSION_SECRET', 'zhiyuan-admin-dev-secret-change-me')


def _session_secret() -> bytes:
    return SESSION_SECRET.encode('utf-8')


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120_000)
    return f'{salt}${digest.hex()}'


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split('$', 1)
    except ValueError:
        return False
    expected = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120_000).hex()
    return hmac.compare_digest(expected, digest)


def ensure_admin_auth() -> None:
    with get_connection() as connection:
        connection.execute(
            '''CREATE TABLE IF NOT EXISTS app_settings (
              setting_key TEXT PRIMARY KEY,
              setting_value TEXT,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )'''
        )
        username_row = row_to_dict(connection.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'admin_username'"
        ).fetchone())
        password_row = row_to_dict(connection.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'admin_password_hash'"
        ).fetchone())
        if not username_row:
            connection.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES ('admin_username', ?)",
                [DEFAULT_USERNAME]
            )
        if not password_row:
            connection.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES ('admin_password_hash', ?)",
                [hash_password(DEFAULT_PASSWORD)]
            )
        connection.commit()


def get_admin_username() -> str:
    ensure_admin_auth()
    with get_connection() as connection:
        row = row_to_dict(connection.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'admin_username'"
        ).fetchone())
    return (row or {}).get('setting_value') or DEFAULT_USERNAME


def verify_admin_credentials(username: str, password: str) -> bool:
    ensure_admin_auth()
    with get_connection() as connection:
        username_row = row_to_dict(connection.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'admin_username'"
        ).fetchone())
        password_row = row_to_dict(connection.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'admin_password_hash'"
        ).fetchone())
    expected_username = (username_row or {}).get('setting_value') or DEFAULT_USERNAME
    stored_hash = (password_row or {}).get('setting_value')
    if not stored_hash:
        stored_hash = hash_password(DEFAULT_PASSWORD)
    return hmac.compare_digest(username, expected_username) and verify_password(password, stored_hash)


def create_session_token(username: str) -> str:
    issued_at = int(time.time())
    payload = f'{username}:{issued_at}'
    signature = hmac.new(_session_secret(), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f'{payload}:{signature}'


def verify_session_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        username, issued_at, signature = token.rsplit(':', 2)
        payload = f'{username}:{issued_at}'
        expected = hmac.new(_session_secret(), payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        if int(time.time()) - int(issued_at) > SESSION_MAX_AGE:
            return None
        if username != get_admin_username():
            return None
        return username
    except (ValueError, TypeError):
        return None


def change_admin_password(old_password: str, new_password: str) -> None:
    if not verify_admin_credentials(get_admin_username(), old_password):
        raise ValueError('原密码不正确')
    if len(new_password or '') < 6:
        raise ValueError('新密码至少 6 位')
    with get_connection() as connection:
        connection.execute(
            "UPDATE app_settings SET setting_value = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = 'admin_password_hash'",
            [hash_password(new_password)]
        )
        connection.commit()


def session_cookie_options() -> dict[str, Any]:
    return {
        'httponly': True,
        'samesite': 'lax',
        'max_age': SESSION_MAX_AGE,
        'path': '/',
    }
