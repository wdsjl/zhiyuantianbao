"""已修复行为的回归契约 — 修改相关模块前必须先跑 test_regression_locks.py。

本文件定义「锁死」的不变量；test_regression_locks.py 与 scripts/verify-regression-locks.ps1 会校验。
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# —— 省份志愿条数 ——
HENAN_BENKE_VOLUNTEER_SLOTS = 48
LEGACY_DEMO_VOLUNTEER_COUNT = 9

# —— 会员 / PDF ——
PREMIUM_PLAN_CODE = 'premium'
PDF_EXPORT_PERMISSION = 'pdf_export'

# —— 虚拟支付发货 ——
VIRTUAL_PAY_WX_ORDER_PREFIX = 'VPO'

# 源码中必须存在 / 不得出现的片段（防回归）
LOCKED_SOURCE_SNIPPETS: dict[str, dict[str, list[str]]] = {
    'pages/volunteer/volunteer.js': {
        'must_contain': [
            'volunteer_count: 0',
            '/api/province-rules/resolve',
            'generation.target_slots',
        ],
        'must_not_contain': [
            'volunteer_count: 9',
        ],
    },
    'pages/schools/schools.js': {
        'must_contain': [
            'normCity',
            'limit: 200',
        ],
        'must_not_contain': [],
    },
    'server/schemas.py': {
        'must_contain': [
            'volunteer_count: int = 0',
        ],
        'must_not_contain': [
            'volunteer_count: int = 9',
        ],
    },
    'server/main.py': {
        'must_contain': [
            "methods=['GET', 'POST']",
            '/api/payments/virtual/deliver-notify',
            'resolve_volunteer_slots(',
            'normalize_volunteer_override(request.volunteer_count)',
            '/api/province-rules/resolve',
            '/api/province-rules/status',
        ],
        'must_not_contain': [
            'total_slots=max(1, int(request.volunteer_count or 9))',
        ],
    },
    'server/membership_service.py': {
        'must_contain': [
            "'pdf_export'",
            'ON CONFLICT(plan_code, permission_code) DO UPDATE',
        ],
        'must_not_contain': [],
    },
    'server/wechat_virtual_pay_service.py': {
        'must_contain': [
            '_split_virtual_pay_ids',
            "notify_id.startswith('VPO')",
            'assume_paid',
            '_xpay_env_candidates',
        ],
        'must_not_contain': [
            "remote_order.get('wxpay_order_id') or remote_order.get('wx_order_id')",
        ],
    },
    'server/province_rules_service.py': {
        'must_contain': [
            '_find_rule_in_catalog',
            "'province': '河南', 'batch': '本科批'",
            "'school_count': 48",
        ],
        'must_not_contain': [],
    },
}


def check_locked_source_files() -> list[str]:
    """返回所有违反契约的说明；空列表表示通过。"""
    errors: list[str] = []
    for rel_path, rules in LOCKED_SOURCE_SNIPPETS.items():
        path = REPO_ROOT / rel_path
        if not path.is_file():
            errors.append(f'缺少锁死文件: {rel_path}')
            continue
        text = path.read_text(encoding='utf-8')
        for snippet in rules.get('must_contain', []):
            if snippet not in text:
                errors.append(f'{rel_path} 缺少必需片段: {snippet!r}')
        for snippet in rules.get('must_not_contain', []):
            if snippet in text:
                errors.append(f'{rel_path} 含已禁止片段: {snippet!r}')
    return errors
