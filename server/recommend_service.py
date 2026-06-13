"""志愿推荐：候选池查询、批次兜底、自动保存草稿。"""

from __future__ import annotations

from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from province_rules_service import _batch_category, _normalize_province, _score_rule_match
from services import matches_subject_requirement

try:
    from crawler_service import normalize_batch_name as normalize_import_batch_name
except ImportError:
    def normalize_import_batch_name(name: str) -> str:
        raw = (name or '').strip()
        mapping = {
            '本科一批': '本科批',
            '本科二批': '本科批',
            '本科': '本科批',
            '专科': '专科批',
        }
        return mapping.get(raw, raw or '本科批')

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
        record_2025 = next((item for item in sorted_records if int(item.get('year') or 0) == ADMISSION_REFERENCE_YEAR), None)
        weighted_items.append({
            **latest,
            'weighted_rank': weighted_rank,
            'weighted_score': weighted_score,
            'years_used': [item['year'] for item in sorted_records],
            'admission_score_2025': (record_2025 or {}).get('min_score'),
            'admission_rank_2025': (record_2025 or {}).get('min_rank'),
        })
    return weighted_items


def build_rank_windows(user_rank: int, segment: str, batch: str) -> list[tuple[int | None, int | None]]:
    from rank_strategy_service import get_band_coefficients, get_pool_rank_window, is_zhuanke_batch

    if not user_rank or user_rank <= 0:
        return [(None, None)]

    base_min, base_max = get_pool_rank_window(user_rank, segment, batch)
    coeffs = get_band_coefficients(segment, batch)
    windows: list[tuple[int | None, int | None]] = [(base_min, base_max)]
    for widen in (1.5, 2.5, 5.0, 10.0):
        lower = max(1, int(user_rank * coeffs['冲'][0] * 0.80 / widen))
        upper = int(user_rank * coeffs['保'][1] * 1.20 * widen)
        if is_zhuanke_batch(batch):
            upper = max(upper, int(user_rank * 1.50 * widen))
        candidate = (lower, upper)
        if candidate not in windows:
            windows.append(candidate)
    windows.append((None, None))
    return windows


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

    rank_windows = build_rank_windows(user_rank or 0, segment, requested_batch) if user_rank and user_rank > 0 else [(None, None)]
    rank_min, rank_max = rank_windows[0]

    meta: dict[str, Any] = {
        'tried_batches': batches,
        'relaxed_major_filter': False,
        'rank_window': [rank_min, rank_max] if rank_min is not None else None,
        'rank_window_relaxed': False,
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
    weighted_items: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    def query_candidates(
        current_major_types: list[str] | None,
        window: tuple[int | None, int | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        window_min, window_max = window
        query_rows, query_batch = _query_rows_for_batches(
            province,
            batches or [requested_batch],
            subject_combination,
            cities=cities,
            school_types=school_types,
            major_types=current_major_types,
            only_public=only_public,
            rank_min=window_min,
            rank_max=window_max,
        )
        return query_rows, build_weighted_items(query_rows), query_batch

    for window_index, window in enumerate(rank_windows):
        rank_min, rank_max = window
        rows, weighted_items, effective_batch = query_candidates(major_types, window)
        if rows and effective_batch and effective_batch != requested_batch:
            meta['batch_fallback'] = effective_batch
        if len(weighted_items) >= total_slots:
            if window_index > 0:
                meta['rank_window_relaxed'] = True
                meta['rank_window'] = [rank_min, rank_max] if rank_min is not None else None
            break

        if major_types:
            relaxed_rows, relaxed_items, relaxed_batch = query_candidates(None, window)
            if relaxed_items and len(relaxed_items) > len(weighted_items):
                rows = relaxed_rows
                weighted_items = relaxed_items
                effective_batch = relaxed_batch
                meta['relaxed_major_filter'] = True
                if relaxed_batch and relaxed_batch != requested_batch:
                    meta['batch_fallback'] = relaxed_batch
            if len(weighted_items) >= total_slots:
                if window_index > 0:
                    meta['rank_window_relaxed'] = True
                    meta['rank_window'] = [rank_min, rank_max] if rank_min is not None else None
                break

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


def _merge_admission_stats(
    stats: dict[tuple[int, int], dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        school_id = row.get('school_id')
        major_id = row.get('major_id')
        if school_id is None or major_id is None:
            continue
        key = (int(school_id), int(major_id))
        existing = stats.get(key)
        if not existing or (row.get('min_rank') is not None and (
            existing.get('min_rank') is None or int(row['min_rank']) < int(existing['min_rank'])
        )):
            stats[key] = row


def _lookup_admission_rows(
    *,
    year: int,
    province: str,
    batch: str,
    school_major_pairs: list[tuple[int, int]] | None = None,
    school_major_codes: list[tuple[str, str]] | None = None,
    use_batch_filter: bool = True,
) -> list[dict[str, Any]]:
    if not school_major_pairs and not school_major_codes:
        return []

    variants = province_variants(province)
    province_placeholders = ','.join(['?'] * len(variants))
    params: list[Any] = [year, *variants]
    batch_clause = ''
    if use_batch_filter:
        batch_aliases = expand_batch_aliases(batch) or [batch]
        batch_placeholders = ','.join(['?'] * len(batch_aliases))
        batch_clause = f' AND batch IN ({batch_placeholders})'
        params.extend(batch_aliases)

    if school_major_pairs:
        pair_placeholders = ','.join(['(?, ?)'] * len(school_major_pairs))
        for school_id, major_id in school_major_pairs:
            params.extend([school_id, major_id])
        sql = f'''
        SELECT school_id, major_id, school_code, major_code, min_score, min_rank, year, batch
        FROM admission_records
        WHERE year = ?
          AND province IN ({province_placeholders}){batch_clause}
          AND (school_id, major_id) IN ({pair_placeholders})
        '''
    else:
        code_placeholders = ','.join(['(?, ?)'] * len(school_major_codes or []))
        for school_code, major_code in school_major_codes or []:
            params.extend([school_code, major_code])
        sql = f'''
        SELECT school_id, major_id, school_code, major_code, min_score, min_rank, year, batch
        FROM admission_records
        WHERE year = ?
          AND province IN ({province_placeholders}){batch_clause}
          AND (school_code, major_code) IN ({code_placeholders})
        '''

    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


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

    stats: dict[tuple[int, int], dict[str, Any]] = {}
    normalized_batch = normalize_import_batch_name(batch)
    for candidate_batch in dict.fromkeys([batch, normalized_batch]):
        _merge_admission_stats(
            stats,
            _lookup_admission_rows(
                year=year,
                province=province,
                batch=candidate_batch,
                school_major_pairs=pairs,
                use_batch_filter=True,
            ),
        )

    missing_pairs = [key for key in pairs if key not in stats]
    if missing_pairs:
        code_pairs: list[tuple[str, str]] = []
        code_to_key: dict[tuple[str, str], tuple[int, int]] = {}
        for item in items:
            school_id = item.get('school_id')
            major_id = item.get('major_id')
            school_code = str(item.get('school_code') or '').strip()
            major_code = str(item.get('major_code') or '').strip()
            if not school_id or not major_id or not school_code or not major_code:
                continue
            key = (int(school_id), int(major_id))
            if key not in missing_pairs:
                continue
            code_key = (school_code, major_code)
            code_pairs.append(code_key)
            code_to_key[code_key] = key
        if code_pairs:
            for candidate_batch in dict.fromkeys([batch, normalized_batch]):
                for row in _lookup_admission_rows(
                    year=year,
                    province=province,
                    batch=candidate_batch,
                    school_major_codes=code_pairs,
                    use_batch_filter=True,
                ):
                    mapped_key = code_to_key.get((str(row.get('school_code') or '').strip(), str(row.get('major_code') or '').strip()))
                    if mapped_key:
                        _merge_admission_stats(stats, [{**row, 'school_id': mapped_key[0], 'major_id': mapped_key[1]}])

    still_missing = [key for key in pairs if key not in stats]
    if still_missing:
        _merge_admission_stats(
            stats,
            _lookup_admission_rows(
                year=year,
                province=province,
                batch=batch,
                school_major_pairs=still_missing,
                use_batch_filter=False,
            ),
        )

    return stats


def attach_admission_year_stats(
    items: list[dict[str, Any]],
    province: str,
    batch: str,
    year: int = ADMISSION_REFERENCE_YEAR,
    *,
    fallback_batch: str | None = None,
) -> list[dict[str, Any]]:
    stats = lookup_admission_stats_by_year(items, province, batch, year)
    if fallback_batch and normalize_import_batch_name(fallback_batch) != normalize_import_batch_name(batch):
        fallback_stats = lookup_admission_stats_by_year(items, province, fallback_batch, year)
        for key, value in fallback_stats.items():
            stats.setdefault(key, value)

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
