import json
import urllib.request

from db import get_connection, row_to_dict

PROVIDER_DEFAULT_BASE_URL = {
    'deepseek': 'https://api.deepseek.com',
    'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
    'openai-compatible': ''
}


def ensure_llm_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS llm_settings (
              setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
              provider TEXT NOT NULL DEFAULT 'openai-compatible',
              base_url TEXT,
              api_key TEXT,
              model_name TEXT,
              temperature REAL NOT NULL DEFAULT 0.7,
              is_enabled INTEGER NOT NULL DEFAULT 0,
              remark TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.commit()


def get_llm_settings() -> dict | None:
    ensure_llm_tables()
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM llm_settings ORDER BY setting_id DESC LIMIT 1').fetchone())


def save_llm_settings(data: dict) -> int:
    ensure_llm_tables()
    existing = get_llm_settings()
    api_key = data.get('api_key') or ''
    if existing and not api_key:
        api_key = existing.get('api_key') or ''
    with get_connection() as connection:
        if existing:
            setting_id = existing['setting_id']
            connection.execute(
                '''
                UPDATE llm_settings SET provider = ?, base_url = ?, api_key = ?, model_name = ?, temperature = ?,
                  is_enabled = ?, remark = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_id = ?
                ''',
                [
                    data.get('provider') or 'openai-compatible', data.get('base_url'), api_key,
                    data.get('model_name'), float(data.get('temperature') or 0.7),
                    1 if data.get('is_enabled') else 0, data.get('remark'), setting_id
                ]
            )
        else:
            cursor = connection.execute(
                '''
                INSERT INTO llm_settings (provider, base_url, api_key, model_name, temperature, is_enabled, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    data.get('provider') or 'openai-compatible', data.get('base_url'), api_key,
                    data.get('model_name'), float(data.get('temperature') or 0.7),
                    1 if data.get('is_enabled') else 0, data.get('remark')
                ]
            )
            setting_id = cursor.lastrowid
        connection.commit()
    return setting_id


def mask_api_key(api_key: str | None) -> str:
    if not api_key:
        return '未配置'
    if len(api_key) <= 8:
        return '*' * len(api_key)
    return f'{api_key[:4]}****{api_key[-4:]}'


def resolve_base_url(settings: dict) -> str:
    base_url = (settings.get('base_url') or '').strip().rstrip('/')
    if base_url:
        return base_url
    provider = settings.get('provider') or 'openai-compatible'
    return PROVIDER_DEFAULT_BASE_URL.get(provider, '').rstrip('/')


def chat_completion(messages: list[dict], max_tokens: int = 256) -> str:
    settings = get_llm_settings()
    if not settings or not settings.get('is_enabled'):
        raise ValueError('大模型未启用')
    if not settings.get('api_key'):
        raise ValueError('请先配置大模型 API Key')
    if not settings.get('model_name'):
        raise ValueError('请先配置模型名称')
    base_url = resolve_base_url(settings)
    if not base_url:
        raise ValueError('请先配置 Base URL')

    url = f'{base_url}/chat/completions'
    payload = {
        'model': settings['model_name'],
        'messages': messages,
        'temperature': float(settings.get('temperature') or 0.7),
        'max_tokens': max_tokens
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings["api_key"]}'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        raise ValueError(f'大模型连接失败：{exc}') from exc

    choices = data.get('choices') or []
    if not choices:
        raise ValueError('大模型响应中没有 choices')
    message = choices[0].get('message') or {}
    content = message.get('content')
    if not content:
        raise ValueError('大模型响应为空')
    return content


def test_llm_connection() -> dict:
    content = chat_completion(
        [
            {'role': 'system', 'content': '你是一个高考志愿填报助手。'},
            {'role': 'user', 'content': '请用一句话回复：大模型连接测试成功。'}
        ],
        max_tokens=64
    )
    return {'ok': True, 'message': content}
