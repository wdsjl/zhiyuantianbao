"""志愿推荐：候选池查询、批次兜底、自动保存草稿。"""

from __future__ import annotations

from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from services import matches_subject_requirement


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
    sql = """
    SELECT ar.*, s.school_name, s.city, s.school_type, s.is_public, s.is_double_first_class,
           m.major_name, m.major_type, ep.tuition, ep.duration, ep.subject_requirement
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    LEFT JOIN enrollment_plans ep ON ep.school_id = ar.school_id
      AND ep.major_id = ar.major_id
      AND ep.province = ar.province
      AND ep.batch = ar.batch
    WHERE ar.province = ? AND ar.batch = ?
    """
    params: list[Any] = [province, batch]

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
    batches: list[str] = []
    for candidate in (batch, rule_batch):
        value = (candidate or '').strip()
        if value and value not in batches:
            batches.append(value)

    meta: dict[str, Any] = {'tried_batches': batches, 'relaxed_major_filter': False}
    rows: list[dict[str, Any]] = []
    effective_batch = batch

    for candidate_batch in batches or [batch]:
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
            effective_batch = candidate_batch
            break

    weighted_items = build_weighted_items(rows)
    if len(weighted_items) < total_slots and major_types:
        for candidate_batch in batches or [batch]:
            relaxed_rows = query_admission_rows(
                province,
                candidate_batch,
                subject_combination,
                cities=cities,
                school_types=school_types,
                major_types=None,
                only_public=only_public,
            )
            if relaxed_rows:
                effective_batch = candidate_batch
                weighted_items = build_weighted_items(relaxed_rows)
                meta['relaxed_major_filter'] = True
                break

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
