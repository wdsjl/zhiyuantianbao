"""志愿推荐：候选池查询、批次兜底、自动保存草稿。"""

from __future__ import annotations

from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from province_rules_service import _normalize_province, _score_rule_match
from services import matches_subject_requirement


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


def _rank_batch_candidates(requested_batch: str, available_batches: list[str]) -> list[str]:
    scored = [(_score_rule_match(requested_batch, batch), batch) for batch in available_batches]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [batch for score, batch in scored if score > 0]


def _build_batch_hint(
    requested_batch: str,
    province: str,
    available_batches: list[dict[str, Any]],
    *,
    batch_fallback: str | None = None,
) -> str:
    if batch_fallback and batch_fallback != requested_batch:
        return (
            f'档案批次为「{requested_batch}」，已自动匹配数据库批次「{batch_fallback}」。'
            '如不符合实际报考批次，请到档案页修改目标批次。'
        )
    if not available_batches:
        normalized = _normalize_province(province) or province
        return f'数据库中未找到「{normalized}」的录取数据，请确认数据已合并到服务器。'
    summary = '、'.join(
        f'{item["batch"]}({int(item.get("school_major_count") or item.get("record_count") or 0)}条)'
        for item in available_batches[:6]
    )
    return (
        f'档案填写批次「{requested_batch}」在库中无匹配数据。'
        f'当前库内批次：{summary}。'
        '请检查档案「目标批次」是否与导入数据一致（如 660 分通常应填本科批，而非专科批）。'
    )


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
    sql = f"""
    SELECT ar.*, s.school_name, s.city, s.school_type, s.is_public, s.is_double_first_class,
           m.major_name, m.major_type, ep.tuition, ep.duration, ep.subject_requirement
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    LEFT JOIN enrollment_plans ep ON ep.school_id = ar.school_id
      AND ep.major_id = ar.major_id
      AND ep.province = ar.province
      AND ep.batch = ar.batch
    WHERE ar.province IN ({province_placeholders}) AND ar.batch = ?
    """
    params: list[Any] = [*province_list, batch]

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


def build_weighted_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row['school_id'], row['major_id'])
        grouped.setdefault(key, []).append(row)

    weighted_items: list[dict[str, Any]] = []
    year_weights = [0.5, 0.3, 0.2]
    for records in grouped.values():
        sorted_records = sorted(records, key=lambda item: item['year'], reverse=True)[:3]
        weight_sum = 0
        rank_sum = 0
        score_sum = 0
        latest = sorted_records[0]
        for index, record in enumerate(sorted_records):
            weight = year_weights[index] if index < len(year_weights) else 0
            if record.get('min_rank') is not None:
                rank_sum += record['min_rank'] * weight
                weight_sum += weight
            if record.get('min_score') is not None:
                score_sum += record['min_score'] * weight
        weighted_rank = round(rank_sum / weight_sum) if weight_sum else latest.get('min_rank')
        weighted_score = round(score_sum / weight_sum) if weight_sum else latest.get('min_score')
        weighted_items.append({
            **latest,
            'weighted_rank': weighted_rank,
            'weighted_score': weighted_score,
            'years_used': [item['year'] for item in sorted_records],
        })
    return weighted_items


def _query_rows_for_batches(
    province: str,
    batch_candidates: list[str],
    subject_combination: str,
    *,
    cities: list[str] | None = None,
    school_types: list[str] | None = None,
    major_types: list[str] | None = None,
    only_public: bool | None = None,
) -> tuple[list[dict[str, Any]], str]:
    for candidate_batch in batch_candidates:
        rows = query_admission_rows(
            province,
            candidate_batch,
            subject_combination,
            cities=cities,
            school_types=school_types,
            major_types=major_types,
            only_public=only_public,
        )
        if rows:
            return rows, candidate_batch
    return [], batch_candidates[0] if batch_candidates else ''


def fetch_recommendation_candidates(
    province: str,
    batch: str,
    subject_combination: str,
    total_slots: int,
    *,
    cities: list[str] | None = None,
    school_types: list[str] | None = None,
    major_types: list[str] | None = None,
    only_public: bool | None = None,
    rule_batch: str | None = None,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    requested_batch = (batch or '').strip()
    batches: list[str] = []
    for candidate in (requested_batch, rule_batch):
        value = (candidate or '').strip()
        if value and value not in batches:
            batches.append(value)

    available_batches = list_province_admission_batches(province)
    available_batch_names = [item['batch'] for item in available_batches if item.get('batch')]
    fallback_batches = _rank_batch_candidates(requested_batch, available_batch_names)
    for candidate in fallback_batches:
        if candidate not in batches:
            batches.append(candidate)

    meta: dict[str, Any] = {
        'tried_batches': batches,
        'relaxed_major_filter': False,
        'available_batches': available_batch_names,
        'available_batch_counts': {
            str(item.get('batch') or ''): int(item.get('school_major_count') or item.get('record_count') or 0)
            for item in available_batches
            if item.get('batch')
        },
        'requested_batch': requested_batch,
        'batch_fallback': None,
        'batch_hint': '',
    }
    effective_batch = requested_batch

    rows, effective_batch = _query_rows_for_batches(
        province,
        batches or [requested_batch],
        subject_combination,
        cities=cities,
        school_types=school_types,
        major_types=major_types,
        only_public=only_public,
    )
    if rows and effective_batch and effective_batch != requested_batch:
        meta['batch_fallback'] = effective_batch

    weighted_items = build_weighted_items(rows)
    if len(weighted_items) < total_slots and major_types:
        relaxed_rows, relaxed_batch = _query_rows_for_batches(
            province,
            batches or [requested_batch],
            subject_combination,
            cities=cities,
            school_types=school_types,
            major_types=None,
            only_public=only_public,
        )
        if relaxed_rows:
            effective_batch = relaxed_batch
            weighted_items = build_weighted_items(relaxed_rows)
            meta['relaxed_major_filter'] = True
            if relaxed_batch and relaxed_batch != requested_batch:
                meta['batch_fallback'] = relaxed_batch

    if not weighted_items:
        meta['batch_hint'] = _build_batch_hint(
            requested_batch,
            province,
            available_batches,
            batch_fallback=meta.get('batch_fallback'),
        )

    meta['candidate_pool'] = len(weighted_items)
    meta['effective_batch'] = effective_batch
    return weighted_items, effective_batch, meta


AUTO_DRAFT_NAME = '智能推荐方案'


def save_auto_recommendation_draft(
    student_id: int,
    province: str,
    batch: str,
    score: int,
    rank: int,
    risk_level: str,
    items: list[dict[str, Any]],
) -> int:
    with get_connection() as connection:
        existing = row_to_dict(
            connection.execute(
                '''
                SELECT draft_id FROM volunteer_drafts
                WHERE student_id = ? AND draft_name = ?
                ORDER BY updated_at DESC, draft_id DESC
                LIMIT 1
                ''',
                [student_id, AUTO_DRAFT_NAME],
            ).fetchone()
        )
        if existing:
            draft_id = int(existing['draft_id'])
            connection.execute(
                '''
                UPDATE volunteer_drafts
                SET province = ?, year = ?, batch = ?, score = ?, rank = ?, risk_level = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE draft_id = ? AND student_id = ?
                ''',
                [province, 2025, batch, score, rank, risk_level, draft_id, student_id],
            )
            connection.execute('DELETE FROM volunteer_draft_items WHERE draft_id = ?', [draft_id])
        else:
            cursor = connection.execute(
                '''
                INSERT INTO volunteer_drafts (
                  student_id, draft_name, province, year, batch, score, rank, risk_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [student_id, AUTO_DRAFT_NAME, province, 2025, batch, score, rank, risk_level],
            )
            draft_id = int(cursor.lastrowid)

        for item in items:
            connection.execute(
                '''
                INSERT INTO volunteer_draft_items (
                  draft_id, sort_order, gradient_type, school_id, school_name, school_code,
                  major_id, major_name, major_code, city, school_type, tuition, duration,
                  is_adjustable, risk_level, risk_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    draft_id,
                    item.get('sort_order'),
                    item.get('gradient_type'),
                    item.get('school_id'),
                    item.get('school_name'),
                    item.get('school_code'),
                    item.get('major_id'),
                    item.get('major_name'),
                    item.get('major_code'),
                    item.get('city'),
                    item.get('school_type'),
                    item.get('tuition'),
                    item.get('duration'),
                    1 if item.get('is_adjustable') else 0,
                    item.get('risk_level'),
                    item.get('risk_reason'),
                ],
            )
        connection.commit()
        return draft_id
