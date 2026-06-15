"""志愿候选池：按分数位次构建全量可报院校专业，并结合偏好排序生成最终方案。"""

from __future__ import annotations

from typing import Any

from db import get_connection, rows_to_dicts
from rank_strategy_service import (
    ADMISSION_PROBABILITY,
    assemble_recommendation_plan,
    build_strategy_meta,
    classify_gradient,
    detect_segment,
    estimate_rank_from_score,
    get_plan_quotas,
)
from schemas import RecommendRequest
from services import get_gradient_type, get_risk_level, get_risk_reason, matches_subject_requirement


def _parse_preferences(preferences: dict[str, Any] | None) -> dict[str, Any]:
    prefs = preferences or {}
    return {
        'preferred_cities': [str(x).strip() for x in (prefs.get('preferredCities') or []) if str(x).strip()],
        'preferred_major_types': [str(x).strip() for x in (prefs.get('preferredMajorTypes') or []) if str(x).strip()],
        'preferred_majors': [str(x).strip() for x in (prefs.get('preferredMajors') or []) if str(x).strip()],
        'avoid_directions': [str(x).strip() for x in (prefs.get('avoidDirections') or []) if str(x).strip()],
        'school_level_preference': str(prefs.get('schoolLevelPreference') or '').strip(),
        'school_nature_preference': str(prefs.get('schoolNaturePreference') or '').strip(),
        'only_public': _nature_to_public(prefs.get('schoolNaturePreference')),
    }


def _nature_to_public(value: Any) -> bool | None:
    text = str(value or '').strip()
    if '公办' in text and '民办' not in text:
        return True
    if '民办' in text and '公办' not in text:
        return False
    return None


def compute_preference_score(
    row: dict[str, Any],
    preferences: dict[str, Any] | None,
    personality_major_types: list[str] | None,
) -> int:
    parsed = _parse_preferences(preferences)
    score = 0
    city = str(row.get('city') or '')
    major_type = str(row.get('major_type') or '')
    major_name = str(row.get('major_name') or '')
    school_name = str(row.get('school_name') or '')

    for avoid in parsed['avoid_directions']:
        if avoid and (avoid in major_name or avoid in major_type or avoid in school_name or avoid in city):
            return -1000

    if parsed['preferred_cities'] and city in parsed['preferred_cities']:
        score += 4
    if parsed['preferred_major_types'] and major_type in parsed['preferred_major_types']:
        score += 3
    for major in parsed['preferred_majors']:
        if major and major in major_name:
            score += 3
            break
    if personality_major_types and major_type in personality_major_types:
        score += 2
    if parsed['school_level_preference']:
        pref = parsed['school_level_preference']
        if '985' in pref and row.get('is_985'):
            score += 2
        elif '211' in pref and row.get('is_211'):
            score += 2
        elif '双一流' in pref and row.get('is_double_first_class'):
            score += 2
    return score


def fetch_admission_rows(request: RecommendRequest) -> list[dict[str, Any]]:
    sql = """
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
    WHERE ar.province = ? AND ar.batch = ?
    """
    params: list[Any] = [request.province, request.batch]

    if request.cities:
        sql += f" AND s.city IN ({','.join(['?'] * len(request.cities))})"
        params.extend(request.cities)
    if request.school_types:
        sql += f" AND s.school_type IN ({','.join(['?'] * len(request.school_types))})"
        params.extend(request.school_types)
    if request.major_types:
        sql += f" AND m.major_type IN ({','.join(['?'] * len(request.major_types))})"
        params.extend(request.major_types)
    only_public = request.only_public
    if only_public is None and getattr(request, 'preferences', None):
        only_public = _nature_to_public((request.preferences or {}).get('schoolNaturePreference'))
    if only_public is not None:
        sql += ' AND s.is_public = ?'
        params.append(1 if only_public else 0)

    sql += ' ORDER BY ar.year DESC, ar.min_rank ASC'

    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())

    return [
        row for row in rows
        if matches_subject_requirement(request.subject_combination, row.get('subject_requirement'))
    ]


def build_weighted_pool(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row['school_id'], row['major_id'])
        grouped.setdefault(key, []).append(row)

    weighted_items: list[dict[str, Any]] = []
    year_weights = [0.5, 0.3, 0.2]
    for records in grouped.values():
        sorted_records = sorted(records, key=lambda item: item['year'], reverse=True)[:3]
        weight_sum = 0.0
        rank_sum = 0.0
        score_sum = 0.0
        latest = sorted_records[0]
        for index, record in enumerate(sorted_records):
            weight = year_weights[index] if index < len(year_weights) else 0.0
            if record.get('min_rank') is not None:
                rank_sum += float(record['min_rank']) * weight
                weight_sum += weight
            if record.get('min_score') is not None:
                score_sum += float(record['min_score']) * weight
        weighted_rank = round(rank_sum / weight_sum) if weight_sum else latest.get('min_rank')
        weighted_score = round(score_sum / weight_sum) if weight_sum else latest.get('min_score')
        weighted_items.append({
            **latest,
            'weighted_rank': weighted_rank,
            'weighted_score': weighted_score,
            'years_used': [item['year'] for item in sorted_records],
        })
    return weighted_items


def resolve_user_rank(request: RecommendRequest, rows: list[dict[str, Any]]) -> int:
    user_rank = int(request.rank or 0)
    if user_rank <= 0 and request.score:
        estimated = estimate_rank_from_score(rows, int(request.score))
        if estimated:
            user_rank = estimated
    return user_rank


def resolve_segment(user_rank: int, province: str, batch: str) -> str:
    with get_connection() as connection:
        total_row = connection.execute(
            'SELECT MAX(min_rank) AS total_rank FROM admission_records WHERE province = ? AND batch = ?',
            [province, batch],
        ).fetchone()
    province_total_rank = total_row['total_rank'] if total_row and total_row['total_rank'] else None
    return detect_segment(user_rank, province_total_rank, batch)


def enrich_pool_items(
    weighted_items: list[dict[str, Any]],
    *,
    user_rank: int,
    segment: str,
    batch: str,
    preferences: dict[str, Any] | None = None,
    personality_major_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in weighted_items:
        school_rank = item.get('weighted_rank') or item.get('min_rank')
        gradient = classify_gradient(user_rank, school_rank, segment, batch)
        enriched.append({
            **item,
            'gradient_type': gradient,
            'admission_probability': ADMISSION_PROBABILITY.get(gradient, ''),
            'preference_score': compute_preference_score(item, preferences, personality_major_types),
            'personality_matched': bool(personality_major_types and item.get('major_type') in personality_major_types),
        })
    return enriched


def sort_pool_for_finalize(pool: list[dict[str, Any]], user_rank: int) -> list[dict[str, Any]]:
    return sorted(
        pool,
        key=lambda row: (
            -int(row.get('preference_score') or 0),
            {'冲': 0, '稳': 1, '保': 2, '垫': 3}.get(row.get('gradient_type', '稳'), 9),
            abs((row.get('weighted_rank') or user_rank) - user_rank),
        ),
    )


def assemble_plan_with_preferences(
    pool: list[dict[str, Any]],
    *,
    user_rank: int,
    plan_style: str,
    batch: str,
    segment: str,
    total_slots: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {'冲': [], '稳': [], '保': [], '垫': []}
    for item in pool:
        gradient = item.get('gradient_type') or classify_gradient(
            user_rank, item.get('weighted_rank') or item.get('min_rank'), segment, batch
        )
        buckets[gradient].append({**item, 'gradient_type': gradient})

    for gradient in buckets:
        buckets[gradient].sort(
            key=lambda row: (
                -int(row.get('preference_score') or 0),
                abs((row.get('weighted_rank') or user_rank) - user_rank),
            )
        )

    quotas = get_plan_quotas(plan_style, batch, total_slots)
    selected: list[dict[str, Any]] = []
    used_keys: set[tuple[Any, Any]] = set()

    def pick_from_bucket(gradient: str, limit: int) -> None:
        count = 0
        for row in buckets[gradient]:
            if count >= limit:
                break
            key = (row.get('school_id'), row.get('major_id'))
            if key in used_keys:
                continue
            selected.append(row)
            used_keys.add(key)
            count += 1

    for gradient in ('冲', '稳', '保'):
        pick_from_bucket(gradient, quotas.get(gradient, 0))

    if len(selected) < total_slots:
        for gradient in ('稳', '保', '垫', '冲'):
            for row in buckets[gradient]:
                if len(selected) >= total_slots:
                    break
                key = (row.get('school_id'), row.get('major_id'))
                if key in used_keys:
                    continue
                selected.append(row)
                used_keys.add(key)

    selected.sort(
        key=lambda row: (
            {'冲': 0, '稳': 1, '保': 2, '垫': 3}.get(row.get('gradient_type', '稳'), 9),
            abs((row.get('weighted_rank') or user_rank) - user_rank),
        )
    )
    meta = build_strategy_meta(user_rank, segment, batch, plan_style, total_slots)
    meta['selected_counts'] = {
        gradient: sum(1 for row in selected if row.get('gradient_type') == gradient)
        for gradient in ('冲', '稳', '保', '垫')
    }
    return selected[:total_slots], meta


def pool_item_to_response(
    row: dict[str, Any],
    *,
    user_rank: int,
    segment: str,
    batch: str,
    accept_adjustment: bool,
    sort_order: int | None = None,
) -> dict[str, Any]:
    gradient_type = row.get('gradient_type') or get_gradient_type(
        user_rank, row.get('weighted_rank') or row.get('min_rank'), segment, batch
    )
    is_adjustable = accept_adjustment
    payload = {
        'gradient_type': gradient_type,
        'school_id': row['school_id'],
        'school_name': row['school_name'],
        'school_code': row.get('school_code'),
        'major_id': row['major_id'],
        'major_name': row['major_name'],
        'major_code': row.get('major_code'),
        'major_type': row.get('major_type'),
        'city': row.get('city'),
        'school_type': row.get('school_type'),
        'tuition': row.get('tuition'),
        'duration': row.get('duration'),
        'min_score': row.get('min_score'),
        'min_rank': row.get('min_rank'),
        'weighted_score': row.get('weighted_score'),
        'weighted_rank': row.get('weighted_rank'),
        'years_used': row.get('years_used'),
        'admission_probability': row.get('admission_probability') or ADMISSION_PROBABILITY.get(gradient_type, ''),
        'preference_score': row.get('preference_score', 0),
        'personality_matched': bool(row.get('personality_matched')),
        'is_adjustable': is_adjustable,
        'risk_level': get_risk_level(gradient_type, is_adjustable),
        'risk_reason': get_risk_reason(gradient_type, is_adjustable),
    }
    if sort_order is not None:
        payload['sort_order'] = sort_order
    return payload


def summarize_pool(pool: list[dict[str, Any]]) -> dict[str, int]:
    summary = {'冲': 0, '稳': 0, '保': 0, '垫': 0, 'total': len(pool)}
    for row in pool:
        gradient = row.get('gradient_type') or '稳'
        if gradient in summary:
            summary[gradient] += 1
    return summary


def build_recommendation_context(request: RecommendRequest) -> dict[str, Any]:
    rows = fetch_admission_rows(request)
    weighted_items = build_weighted_pool(rows)
    user_rank = resolve_user_rank(request, rows)
    segment = resolve_segment(user_rank, request.province, request.batch)
    preferences = getattr(request, 'preferences', None) or {}
    personality_major_types = getattr(request, 'personality_major_types', None) or []
    pool = enrich_pool_items(
        weighted_items,
        user_rank=user_rank,
        segment=segment,
        batch=request.batch,
        preferences=preferences,
        personality_major_types=personality_major_types,
    )
    return {
        'rows': rows,
        'weighted_items': weighted_items,
        'pool': pool,
        'user_rank': user_rank,
        'segment': segment,
    }


def query_eligible_pool(
    request: RecommendRequest,
    *,
    gradient: str = '',
    keyword: str = '',
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    context = build_recommendation_context(request)
    pool = context['pool']
    if gradient:
        pool = [row for row in pool if row.get('gradient_type') == gradient]
    if keyword:
        keyword_lower = keyword.lower()
        pool = [
            row for row in pool
            if keyword_lower in str(row.get('school_name') or '').lower()
            or keyword_lower in str(row.get('major_name') or '').lower()
            or keyword_lower in str(row.get('city') or '').lower()
        ]

    pool.sort(
        key=lambda row: (
            {'冲': 0, '稳': 1, '保': 2, '垫': 3}.get(row.get('gradient_type', '稳'), 9),
            abs((row.get('weighted_rank') or context['user_rank']) - context['user_rank']),
        )
    )

    total = len(pool)
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    start = (page - 1) * page_size
    page_rows = pool[start:start + page_size]
    items = [
        pool_item_to_response(
            row,
            user_rank=context['user_rank'],
            segment=context['segment'],
            batch=request.batch,
            accept_adjustment=request.accept_adjustment,
        )
        for row in page_rows
    ]
    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'summary': summarize_pool(context['pool']),
        'strategy': build_strategy_meta(
            context['user_rank'],
            context['segment'],
            request.batch,
            request.plan_style or 'balanced',
            max(1, int(request.volunteer_count or 9)),
        ),
        'user_rank': context['user_rank'],
    }


def build_final_recommendation(request: RecommendRequest) -> dict[str, Any]:
    context = build_recommendation_context(request)
    pool = sort_pool_for_finalize(context['pool'], context['user_rank'])
    total_slots = max(1, int(request.volunteer_count or 9))
    selected_rows, strategy_meta = assemble_plan_with_preferences(
        pool,
        user_rank=context['user_rank'],
        plan_style=request.plan_style or 'balanced',
        batch=request.batch,
        segment=context['segment'],
        total_slots=total_slots,
    )
    items = [
        pool_item_to_response(
            row,
            user_rank=context['user_rank'],
            segment=context['segment'],
            batch=request.batch,
            accept_adjustment=request.accept_adjustment,
            sort_order=index,
        )
        for index, row in enumerate(selected_rows, start=1)
    ]
    from services import inspect_plan_risk

    return {
        'items': items,
        'risk': inspect_plan_risk(items),
        'strategy': strategy_meta,
        'algorithm': strategy_meta.get('algorithm'),
        'pool_summary': summarize_pool(context['pool']),
    }
