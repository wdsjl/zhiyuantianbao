"""录取数据批次查询与候选池数据拉取。"""

from __future__ import annotations

from typing import Any

from db import get_connection, rows_to_dicts
from province_rules_service import _normalize_province
from services import matches_subject_requirement

BATCH_ALIAS_GROUPS: dict[str, list[str]] = {
    '本科批': ['本科批', '本科', '本科普通批', '普通本科批', '本科一批', '本科二批'],
    '专科批': ['专科批', '专科', '高职专科批', '高职高专批', '高专批'],
    '本科提前批': ['本科提前批', '本科提前', '提前批本科'],
    '专科提前批': ['专科提前批', '专科提前', '提前批专科'],
    '普通类一段': ['普通类一段', '平行录取一段', '普通类平行录取一段'],
    '普通类二段': ['普通类二段', '平行录取二段'],
}


def expand_batch_aliases(batch: str) -> list[str]:
    requested = (batch or '').strip()
    variants: list[str] = []
    if requested:
        variants.append(requested)
    for aliases in BATCH_ALIAS_GROUPS.values():
        if requested in aliases:
            for alias in aliases:
                if alias not in variants:
                    variants.append(alias)
    if requested and '本科' in requested and '专科' not in requested:
        for alias in BATCH_ALIAS_GROUPS['本科批']:
            if alias not in variants:
                variants.append(alias)
    if requested and '专科' in requested:
        for alias in BATCH_ALIAS_GROUPS['专科批']:
            if alias not in variants:
                variants.append(alias)
    return variants or [requested]


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


def query_admission_rows(
    province: str,
    batch: str,
    subject_combination: str,
    *,
    cities: list[str] | None = None,
    school_types: list[str] | None = None,
    major_types: list[str] | None = None,
    only_public: bool | None = None,
) -> list[dict[str, Any]]:
    province_list = province_variants(province)
    province_placeholders = ','.join(['?'] * len(province_list))
    batch_list = expand_batch_aliases(batch) or ['']
    batch_placeholders = ','.join(['?'] * len(batch_list))
    sql = f"""
    SELECT ar.*, s.school_name, s.city, s.school_type, s.is_public, s.is_985, s.is_211,
           s.is_double_first_class, m.major_name, m.major_type, ep.tuition, ep.duration,
           ep.subject_requirement
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    LEFT JOIN enrollment_plans ep ON ep.school_id = ar.school_id
      AND ep.major_id = ar.major_id
      AND ep.province = ar.province
      AND ep.batch = ar.batch
    WHERE ar.province IN ({province_placeholders}) AND ar.batch IN ({batch_placeholders})
    """
    params: list[Any] = [*province_list, *batch_list]

    if cities:
        sql += f" AND s.city IN ({','.join(['?'] * len(cities))})"
        params.extend(cities)
    if school_types:
        sql += f" AND s.school_type IN ({','.join(['?'] * len(school_types))})"
        params.extend(school_types)
    if major_types:
        sql += f" AND m.major_type IN ({','.join(['?'] * len(major_types))})"
        params.extend(major_types)
    if only_public is not None:
        sql += ' AND s.is_public = ?'
        params.append(1 if only_public else 0)

    sql += ' ORDER BY ar.year DESC, ar.min_rank ASC'

    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())

    return [
        row for row in rows
        if matches_subject_requirement(subject_combination, row.get('subject_requirement'))
    ]
