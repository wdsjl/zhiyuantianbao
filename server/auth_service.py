import json
import os
import urllib.parse
import urllib.request
from typing import Any

from db import get_connection, row_to_dict

WECHAT_SESSION_URL = 'https://api.weixin.qq.com/sns/jscode2session'


def normalize_role(role: str) -> str:
    if role in ['学生', 'student']:
        return 'student'
    if role in ['家长', 'parent']:
        return 'parent'
    if role in ['teacher', 'admin']:
        return role
    return 'student'


def get_wechat_session(code: str) -> dict[str, Any] | None:
    appid = os.getenv('WECHAT_APPID', '')
    secret = os.getenv('WECHAT_SECRET', '')
    if not appid or not secret or not code:
        return None

    query = urllib.parse.urlencode({
        'appid': appid,
        'secret': secret,
        'js_code': code,
        'grant_type': 'authorization_code'
    })
    with urllib.request.urlopen(f'{WECHAT_SESSION_URL}?{query}', timeout=8) as response:
        data = json.loads(response.read().decode('utf-8'))
    if data.get('errcode'):
        raise ValueError(data.get('errmsg', '微信登录失败'))
    return data


def login_or_create_user(code: str | None, openid: str | None, phone: str | None, name: str | None, role: str) -> dict[str, Any]:
    session = get_wechat_session(code or '')
    resolved_openid = openid or (session or {}).get('openid') or f'dev_{code or phone or name or "student"}'
    unionid = (session or {}).get('unionid')
    normalized_role = normalize_role(role)

    with get_connection() as connection:
        user = row_to_dict(connection.execute('SELECT * FROM users WHERE openid = ?', [resolved_openid]).fetchone())
        if not user and phone:
            user = row_to_dict(connection.execute('SELECT * FROM users WHERE phone = ?', [phone]).fetchone())

        if user:
            user_id = user['user_id']
            connection.execute(
                '''
                UPDATE users SET openid = ?, unionid = ?, phone = COALESCE(?, phone), role = ?,
                  name = COALESCE(?, name), updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                ''',
                [resolved_openid, unionid, phone, normalized_role, name, user_id]
            )
        else:
            cursor = connection.execute(
                'INSERT INTO users (openid, unionid, phone, role, name) VALUES (?, ?, ?, ?, ?)',
                [resolved_openid, unionid, phone, normalized_role, name]
            )
            user_id = cursor.lastrowid

        profile = row_to_dict(connection.execute(
            '''
            SELECT u.user_id, u.openid, u.phone, u.role, u.name, s.student_id, s.province, s.city,
                   s.school_name, s.grade, s.class_name, s.exam_year, s.exam_type,
                   s.subject_combination, s.score, s.rank, s.target_batch
            FROM users u
            LEFT JOIN students s ON s.user_id = u.user_id
            WHERE u.user_id = ?
            ORDER BY s.student_id DESC LIMIT 1
            ''',
            [user_id]
        ).fetchone())
        connection.commit()

    return {
        'user_id': user_id,
        'openid': resolved_openid,
        'unionid': unionid,
        'has_profile': bool(profile and profile.get('student_id')),
        'profile': profile
    }
