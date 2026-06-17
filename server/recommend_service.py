"""录取数据批次查询等推荐辅助能力。"""

from __future__ import annotations

from typing import Any

from db import get_connection, rows_to_dicts
from province_rules_service import _normalize_province


def province_variants(province: str) -> list[str]:
    base = _normalize_province(province)
    variants: list[str] = []
    for value in ((province or '').strip(), base, f'{base}省', f'{base}市'):
        if value and value not in variants:
            variants.append(value)
    return variants or [(province or '').strip()]


def list_province_admission_batches(province: str) -> list[dict[str, Any]]:
    variants = province_variants(province)
    placeholders = ','.join(['?'] * len(variants))
    with get_connection() as connection:
        rows = rows_to_dicts(
            connection.execute(
                f'''
                SELECT batch,
                       COUNT(*) AS record_count,
                       COUNT(DISTINCT school_id || '-' || major_id) AS school_major_count
                FROM admission_records
                WHERE province IN ({placeholders})
                GROUP BY batch
                ORDER BY school_major_count DESC, record_count DESC
                ''',
                variants,
            ).fetchall()
        )
    return rows
