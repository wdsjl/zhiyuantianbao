"""从 ecosystem.secrets.js / local.secrets.env 兜底加载密钥到环境变量。"""

from __future__ import annotations

import os
import re
import sys
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
_secrets_source: str = ''
_candidate_paths: list[Path] = []


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_candidate_secret_paths() -> list[Path]:
    global _candidate_paths
    if _candidate_paths:
        return _candidate_paths

    root = _project_root()
    env_root = (os.getenv('ZHIYUAN_ROOT') or '').strip()
    paths = [
        root / 'ecosystem.secrets.js',
        root / 'server' / 'local.secrets.env',
        Path('C:/zhiyuantianbao/ecosystem.secrets.js'),
        Path('C:/zhiyuantianbao/server/local.secrets.env'),
    ]
    if env_root:
        paths.insert(0, Path(env_root) / 'ecosystem.secrets.js')
        paths.insert(1, Path(env_root) / 'server' / 'local.secrets.env')

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    _candidate_paths = deduped
    return deduped


def get_secrets_file_path() -> Path:
    for path in get_candidate_secret_paths():
        if path.exists():
            return path
    return get_candidate_secret_paths()[0]


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


def _parse_env_file(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.splitlines():
        text = line.strip()
        if not text or text.startswith('#') or '=' not in text:
            continue
        key, value = text.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in SECRET_KEYS and value:
            values[key] = value
    return values


def _parse_secret_file(path: Path, content: str) -> dict[str, str]:
    if path.suffix == '.env':
        return _parse_env_file(content)
    return _parse_secrets_js(content)


def load_ecosystem_secrets(force: bool = False) -> dict[str, str]:
    global _loaded_from_file, _secrets_source
    loaded: dict[str, str] = {}
    _loaded_from_file = []
    _secrets_source = ''

    for path in get_candidate_secret_paths():
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding='utf-8-sig')
        except OSError:
            continue

        parsed = _parse_secret_file(path, content)
        if not parsed:
            continue

        _secrets_source = str(path)
        for key, value in parsed.items():
            if force or not (os.getenv(key) or '').strip():
                os.environ[key] = value
                loaded[key] = value
                if key not in _loaded_from_file:
                    _loaded_from_file.append(key)

        if loaded:
            print(
                f'[bootstrap] loaded secrets from {path}: {", ".join(loaded.keys())}',
                file=sys.stderr,
            )
            break

    if not loaded:
        print(
            f'[bootstrap] no secrets loaded. checked: {", ".join(str(p) for p in get_candidate_secret_paths())}',
            file=sys.stderr,
        )

    return loaded


def get_secrets_bootstrap_status() -> dict[str, object]:
    return {
        'secrets_source': _secrets_source,
        'secrets_file': str(get_secrets_file_path()),
        'secrets_file_exists': get_secrets_file_path().exists(),
        'candidate_paths': [str(path) for path in get_candidate_secret_paths()],
        'loaded_from_file': list(_loaded_from_file),
        'douyin_app_secret_in_env': bool((os.getenv('DOUYIN_APP_SECRET') or '').strip()),
        'douyin_spi_token_in_env': bool((os.getenv('DOUYIN_SPI_TOKEN') or '').strip()),
    }
