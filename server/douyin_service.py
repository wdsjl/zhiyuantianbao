"""抖音开放平台基础能力：配置读取、client_token 缓存。"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

DOUYIN_OPEN_API_HOST = 'https://open.douyin.com'

_token_cache: dict[str, Any] = {
    'access_token': '',
    'expires_at': 0,
}


def get_douyin_config() -> dict[str, str]:
    return {
        'app_id': (os.getenv('DOUYIN_APP_ID') or '').strip(),
        'app_secret': (os.getenv('DOUYIN_APP_SECRET') or '').strip(),
        'spi_token': (os.getenv('DOUYIN_SPI_TOKEN') or '').strip(),
    }


def get_douyin_status() -> dict[str, Any]:
    config = get_douyin_config()
    missing: list[str] = []
    if not config['app_id']:
        missing.append('DOUYIN_APP_ID')
    if not config['app_secret']:
        missing.append('DOUYIN_APP_SECRET')
    status: dict[str, Any] = {
        'enabled': not missing,
        'app_id': config['app_id'],
        'app_id_configured': bool(config['app_id']),
        'app_secret_configured': bool(config['app_secret']),
        'spi_token_configured': bool(config['spi_token']),
        'missing': missing,
        'hint': (
            '请在 ecosystem.secrets.js 配置 DOUYIN_APP_SECRET 后执行 pm2 restart zhiyuan-backend --update-env'
            if missing else '抖音开放平台凭证已配置，可进行发券 SPI 与微信兑券。'
        ),
    }
    if not missing:
        try:
            token = get_client_token(force_refresh=False)
            status['client_token_ok'] = bool(token)
        except Exception as exc:
            status['client_token_ok'] = False
            status['client_token_error'] = str(exc)
    return status


def get_client_token(force_refresh: bool = False) -> str:
    config = get_douyin_config()
    if not config['app_id'] or not config['app_secret']:
        raise ValueError('未配置 DOUYIN_APP_ID / DOUYIN_APP_SECRET')

    now = int(time.time())
    if (
        not force_refresh
        and _token_cache.get('access_token')
        and int(_token_cache.get('expires_at') or 0) > now + 120
    ):
        return str(_token_cache['access_token'])

    payload = json.dumps({
        'client_key': config['app_id'],
        'client_secret': config['app_secret'],
        'grant_type': 'client_credential',
    }).encode('utf-8')
    request = urllib.request.Request(
        f'{DOUYIN_OPEN_API_HOST}/oauth/client_token/',
        data=payload,
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            body = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise ValueError(f'获取抖音 client_token 失败：{detail or exc.reason}') from exc

    data = body.get('data') or {}
    if str(data.get('error_code')) not in ('0', '0.0', '', 'None') and data.get('error_code') not in (0, None):
        raise ValueError(data.get('description') or body.get('message') or '获取抖音 client_token 失败')

    token = data.get('access_token') or ''
    if not token:
        raise ValueError('抖音 client_token 为空')

    expires_in = int(data.get('expires_in') or 7200)
    _token_cache['access_token'] = token
    _token_cache['expires_at'] = now + max(300, expires_in - 300)
    return token
