from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts

PLAN_CATALOG: dict[str, dict[str, str]] = {
    'trial': {
        'plan_name': '普通卡',
        'description': '引流体验卡，含基础查询与测评；不含智能推荐、AI 报告与 PDF 导出',
    },
    'premium': {
        'plan_name': '白金卡',
        'description': '报考季全功能畅享，智能推荐、AI 报告、PDF 导出不限次',
    },
}


def ensure_bean_tables() -> None:
    """保留空实现，兼容旧库表；星鼎豆体系已下线。"""
    return None


def apply_plan_catalog(plan: dict[str, Any] | None) -> dict[str, Any]:
    if not plan:
        return {}
    code = str(plan.get('plan_code') or '')
    meta = PLAN_CATALOG.get(code, {})
    enriched = dict(plan)
    if meta:
        enriched['plan_name'] = meta['plan_name']
        enriched['description'] = meta['description']
    return enriched


def sync_plan_catalog() -> None:
    from membership_service import ensure_membership_tables
    ensure_membership_tables()
    with get_connection() as connection:
        for plan_code, meta in PLAN_CATALOG.items():
            connection.execute(
                '''
                UPDATE membership_plans
                SET plan_name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE plan_code = ?
                ''',
                [meta['plan_name'], meta['description'], plan_code],
            )
        connection.commit()
