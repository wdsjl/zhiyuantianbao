"""从 ecosystem.secrets.js 兜底加载密钥到环境变量（解决 PM2 未注入 env 的问题）。"""

from __future__ import annotations

import os
import re
from pathlib import Path

SECRET_KEYS = (
    'WECHAT_SECRET',
    'WECHAT_VIRTUAL_PAY_APP_KEY',
    'WECHAT_VIRTUAL_PAY_SANDBOX_APP_KEY',
    'WECHAT_PAY_API_V3_KEY',
    'WECHAT_PAY_SERIAL_NO',
    'DOUYIN_APP_SECRET',
    'DOUYIN_SPI_TOKEN',
)

_loaded_from_file: list[str] = []
_secrets_path: Path | None = None


def get_secrets_file_path() -> Path:
    global _secrets_path
    if _secrets_path is None:
        _secrets_path = Path(__file__).resolve().parents[1] / 'ecosystem.secrets.js'
    return _secrets_path


def _parse_secrets_js(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in SECRET_KEYS:
        match = re.search(
            rf"{re.escape(key)}\s*:\s*['\"]([^'\"]*)['\"]",
            content,
        )
        if match:
            value = (match.group(1) or '').strip()
            if value:
                values[key] = value
    return values


def load_ecosystem_secrets(force: bool = False) -> dict[str, str]:
    global _loaded_from_file
    path = get_secrets_file_path()
    loaded: dict[str, str] = {}

    if not path.exists():
        _loaded_from_file = []
        return loaded

    try:
        content = path.read_text(encoding='utf-8-sig')
    except OSError:
        _loaded_from_file = []
        return loaded

    parsed = _parse_secrets_js(content)
    for key, value in parsed.items():
        if force or not (os.getenv(key) or '').strip():
            os.environ[key] = value
            loaded[key] = value
            if key not in _loaded_from_file:
                _loaded_from_file.append(key)

    return loaded


def get_secrets_bootstrap_status() -> dict[str, object]:
    path = get_secrets_file_path()
    return {
        'secrets_file': str(path),
        'secrets_file_exists': path.exists(),
        'loaded_from_file': list(_loaded_from_file),
        'douyin_app_secret_in_env': bool((os.getenv('DOUYIN_APP_SECRET') or '').strip()),
        'douyin_spi_token_in_env': bool((os.getenv('DOUYIN_SPI_TOKEN') or '').strip()),
    }
