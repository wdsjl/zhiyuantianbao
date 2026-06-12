"""志愿推荐：候选池查询、批次兜底、自动保存草稿。"""

from __future__ import annotations

from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from province_rules_service import _batch_category, _normalize_province, _score_rule_match
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
    suggested = ''
    if available_batches:
        undergrad = [item for item in available_batches if _batch_category(str(item.get('batch') or '')) != 'junior']
        junior = [item for item in available_batches if _batch_category(str(item.get('batch') or '')) == 'junior']
        if undergrad and _batch_category(requested_batch) == 'junior':
            top = undergrad[0].get('batch')
            suggested = f' 建议将目标批次改为「{top}」。'
    return (
        f'档案填写批次「{requested_batch}」在库中无匹配数据。'
        f'当前库内批次：{summary}。'
        f'请检查档案「目标批次」是否与导入数据一致（如 660 分通常应填本科批，而非专科批）。{suggested}'
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
    rank_min: int | None = None,
    rank_max: int | None = None,
) -> list[dict[str, Any]]:
    province_list = province_variants(province)
    province_placeholders = ','.join(['?'] * len(province_list))
    batch_list = expand_batch_aliases(batch) or ['']
    batch_placeholders = ','.join(['?'] * len(batch_list))
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
    if rank_min is not None:
        sql += ' AND ar.min_rank IS NOT NULL AND ar.min_rank >= ?'
        params.append(int(rank_min))
    if rank_max is not None:
        sql += ' AND ar.min_rank IS NOT NULL AND ar.min_rank <= ?'
        params.append(int(rank_max))

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
        weighted_rank = round(rank_sum / weight_sum) if weight_sum else None
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
    rank_min: int | None = None,
    rank_max: int | None = None,
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
            rank_min=rank_min,
            rank_max=rank_max,
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
    user_rank: int | None = None,
    segment: str = 'mid',
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    requested_batch = (batch or '').strip()
    batches: list[str] = []
    for candidate in (requested_batch, rule_batch):
        for alias in expand_batch_aliases((candidate or '').strip()):
            if alias and alias not in batches:
                batches.append(alias)

    available_batches = list_province_admission_batches(province)
    available_batch_names = [item['batch'] for item in available_batches if item.get('batch')]
    fallback_batches = _rank_batch_candidates(requested_batch, available_batch_names)
    for candidate in fallback_batches:
        for alias in expand_batch_aliases(candidate):
            if alias and alias not in batches:
                batches.append(alias)

    rank_min: int | None = None
    rank_max: int | None = None
    if user_rank and user_rank > 0:
        from rank_strategy_service import get_pool_rank_window
        rank_min, rank_max = get_pool_rank_window(user_rank, segment, requested_batch)

    meta: dict[str, Any] = {
        'tried_batches': batches,
        'relaxed_major_filter': False,
        'rank_window': [rank_min, rank_max] if rank_min is not None else None,
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
        rank_min=rank_min,
        rank_max=rank_max,
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
            rank_min=rank_min,
            rank_max=rank_max,
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
ADMISSION_REFERENCE_YEAR = 2025


def ensure_draft_item_admission_columns() -> None:
    with get_connection() as connection:
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(volunteer_draft_items)').fetchall()}
        changed = False
        if 'admission_score_2025' not in columns:
            connection.execute('ALTER TABLE volunteer_draft_items ADD COLUMN admission_score_2025 INTEGER')
            changed = True
        if 'admission_rank_2025' not in columns:
            connection.execute('ALTER TABLE volunteer_draft_items ADD COLUMN admission_rank_2025 INTEGER')
            changed = True
        if changed:
            connection.commit()


def lookup_admission_stats_by_year(
    items: list[dict[str, Any]],
    province: str,
    batch: str,
    year: int = ADMISSION_REFERENCE_YEAR,
) -> dict[tuple[int, int], dict[str, Any]]:
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for item in items:
        school_id = item.get('school_id')
        major_id = item.get('major_id')
        if not school_id or not major_id:
            continue
        key = (int(school_id), int(major_id))
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    if not pairs:
        return {}

    variants = province_variants(province)
    province_placeholders = ','.join(['?'] * len(variants))
    batch_aliases = expand_batch_aliases(batch) or [batch]
    batch_placeholders = ','.join(['?'] * len(batch_aliases))
    pair_placeholders = ','.join(['(?, ?)'] * len(pairs))
    params: list[Any] = [year, *variants, *batch_aliases]
    for school_id, major_id in pairs:
        params.extend([school_id, major_id])

    sql = f'''
    SELECT school_id, major_id, min_score, min_rank, year, batch
    FROM admission_records
    WHERE year = ?
      AND province IN ({province_placeholders})
      AND batch IN ({batch_placeholders})
      AND (school_id, major_id) IN ({pair_placeholders})
    '''
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())
    stats: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        key = (int(row['school_id']), int(row['major_id']))
        existing = stats.get(key)
        if not existing or (row.get('min_rank') is not None and (
            existing.get('min_rank') is None or int(row['min_rank']) < int(existing['min_rank'])
        )):
            stats[key] = row
    return stats


def attach_admission_year_stats(
    items: list[dict[str, Any]],
    province: str,
    batch: str,
    year: int = ADMISSION_REFERENCE_YEAR,
) -> list[dict[str, Any]]:
    stats = lookup_admission_stats_by_year(items, province, batch, year)
    enriched: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        if row.get('admission_score_2025') is None and row.get('admission_rank_2025') is None:
            key = (int(row.get('school_id') or 0), int(row.get('major_id') or 0))
            stat = stats.get(key) or {}
            row['admission_score_2025'] = stat.get('min_score')
            row['admission_rank_2025'] = stat.get('min_rank')
        enriched.append(row)
    return enriched


def save_auto_recommendation_draft(
    student_id: int,
    province: str,
    batch: str,
    score: int,
    rank: int,
    risk_level: str,
    items: list[dict[str, Any]],
) -> int:
    ensure_draft_item_admission_columns()
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
                  is_adjustable, risk_level, risk_reason, admission_score_2025, admission_rank_2025
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    item.get('admission_score_2025'),
                    item.get('admission_rank_2025'),
                ],
            )
        connection.commit()
        return draft_id
