"""微信小程序 URL Scheme / URL Link 生成。"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

WECHAT_API_HOST = 'https://api.weixin.qq.com'
DEFAULT_ENV_VERSION = os.getenv('WECHAT_LINK_ENV_VERSION', 'release')
SCHEME_EXPIRE_DAYS = int(os.getenv('WECHAT_SCHEME_EXPIRE_DAYS', '30'))
URL_LINK_EXPIRE_DAYS = int(os.getenv('WECHAT_URL_LINK_EXPIRE_DAYS', '30'))

_token_cache: dict[str, Any] = {
    'access_token': '',
    'expires_at': 0,
}
_link_cache: dict[str, dict[str, Any]] = {}


def _normalize_page_path(path: str) -> str:
    text = (path or 'pages/home/home').strip().lstrip('/')
    return text or 'pages/home/home'


def _normalize_query(query: str | dict[str, str] | None) -> str:
    if not query:
        return ''
    if isinstance(query, dict):
        parts = [f'{key}={value}' for key, value in query.items() if value not in (None, '')]
        return '&'.join(parts)
    return str(query).strip().lstrip('?')


def get_wechat_access_token(force_refresh: bool = False) -> str:
    appid = (os.getenv('WECHAT_APPID') or '').strip()
    secret = (os.getenv('WECHAT_SECRET') or '').strip()
    if not appid or not secret:
        raise ValueError('未配置 WECHAT_APPID / WECHAT_SECRET，无法生成小程序跳转链接')

    now = int(time.time())
    if (
        not force_refresh
        and _token_cache.get('access_token')
        and int(_token_cache.get('expires_at') or 0) > now + 120
    ):
        return str(_token_cache['access_token'])

    query = urllib.parse.urlencode({
        'grant_type': 'client_credential',
        'appid': appid,
        'secret': secret,
    })
    with urllib.request.urlopen(f'{WECHAT_API_HOST}/cgi-bin/token?{query}', timeout=12) as response:
        data = json.loads(response.read().decode('utf-8'))
    if data.get('errcode'):
        raise ValueError(data.get('errmsg', '获取 access_token 失败'))
    token = data.get('access_token') or ''
    if not token:
        raise ValueError('获取 access_token 失败')
    _token_cache['access_token'] = token
    _token_cache['expires_at'] = now + int(data.get('expires_in') or 7200) - 300
    return token


def _post_wechat_api(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = get_wechat_access_token()
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        f'{WECHAT_API_HOST}{path}?access_token={token}',
        data=body,
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise ValueError(f'微信接口调用失败：{detail or exc.reason}') from exc
    if data.get('errcode') not in (0, None):
        raise ValueError(data.get('errmsg') or f'微信接口错误：{data.get("errcode")}')
    return data


def _cache_key(kind: str, page_path: str, query: str, env_version: str) -> str:
    raw = f'{kind}:{page_path}:{query}:{env_version}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _read_cache(key: str) -> dict[str, Any] | None:
    item = _link_cache.get(key)
    if not item:
        return None
    if int(item.get('expires_at') or 0) <= int(time.time()):
        _link_cache.pop(key, None)
        return None
    return item


def _write_cache(key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    _link_cache[key] = {
        **value,
        'expires_at': int(time.time()) + ttl_seconds,
    }


def generate_url_scheme(
    page_path: str = 'pages/home/home',
    query: str | dict[str, str] | None = None,
    *,
    env_version: str | None = None,
    expire_days: int | None = None,
) -> dict[str, Any]:
    path = _normalize_page_path(page_path)
    query_text = _normalize_query(query)
    version = env_version or DEFAULT_ENV_VERSION
    cache_key = _cache_key('scheme', path, query_text, version)
    cached = _read_cache(cache_key)
    if cached:
        return cached

    days = expire_days if expire_days is not None else SCHEME_EXPIRE_DAYS
    expire_time = int(time.time()) + max(1, days) * 86400
    payload = {
        'jump_wxa': {
            'path': path,
            'query': query_text,
            'env_version': version,
        },
        'is_expire': True,
        'expire_time': expire_time,
    }
    data = _post_wechat_api('/wxa/generatescheme', payload)
    result = {
        'url_scheme': data.get('openlink') or '',
        'page_path': path,
        'query': query_text,
        'env_version': version,
        'expire_time': expire_time,
    }
    if not result['url_scheme']:
        raise ValueError('微信未返回 URL Scheme')
    _write_cache(cache_key, result, max(300, days * 86400 - 600))
    return result


def generate_url_link(
    page_path: str = 'pages/home/home',
    query: str | dict[str, str] | None = None,
    *,
    env_version: str | None = None,
    expire_days: int | None = None,
) -> dict[str, Any]:
    path = _normalize_page_path(page_path)
    query_text = _normalize_query(query)
    version = env_version or DEFAULT_ENV_VERSION
    cache_key = _cache_key('urllink', path, query_text, version)
    cached = _read_cache(cache_key)
    if cached:
        return cached

    days = expire_days if expire_days is not None else URL_LINK_EXPIRE_DAYS
    payload = {
        'path': path,
        'query': query_text,
        'env_version': version,
        'expire_type': 1,
        'expire_interval': max(1, days),
    }
    data = _post_wechat_api('/wxa/generate_urllink', payload)
    result = {
        'url_link': data.get('url_link') or '',
        'page_path': path,
        'query': query_text,
        'env_version': version,
        'expire_interval_days': max(1, days),
    }
    if not result['url_link']:
        raise ValueError('微信未返回 URL Link')
    _write_cache(cache_key, result, max(300, days * 86400 - 600))
    return result


def generate_mini_program_links(
    page_path: str = 'pages/home/home',
    query: str | dict[str, str] | None = None,
    *,
    env_version: str | None = None,
) -> dict[str, Any]:
    path = _normalize_page_path(page_path)
    query_text = _normalize_query(query)
    scheme = generate_url_scheme(path, query_text, env_version=env_version)
    url_link = generate_url_link(path, query_text, env_version=env_version)
    return {
        'page_path': path,
        'query': query_text,
        'share_path': f'{path}?{query_text}' if query_text else path,
        'url_scheme': scheme.get('url_scheme'),
        'url_link': url_link.get('url_link'),
        'scheme_expire_time': scheme.get('expire_time'),
        'url_link_expire_days': url_link.get('expire_interval_days'),
        'env_version': env_version or DEFAULT_ENV_VERSION,
    }
