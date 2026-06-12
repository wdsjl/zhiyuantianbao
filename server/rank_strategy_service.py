from __future__ import annotations

from typing import Any

PLAN_STYLES: dict[str, dict[str, int]] = {
    'balanced': {'冲': 2, '稳': 5, '保': 2},
    'aggressive': {'冲': 3, '稳': 4, '保': 2},
    'conservative': {'冲': 1, '稳': 5, '保': 3},
}

PLAN_STYLES_ZHUANKE: dict[str, int] = {'冲': 1, '稳': 4, '保': 4}

ADMISSION_PROBABILITY = {
    '冲': '30%-50%',
    '稳': '80%+',
    '保': '98%+',
    '垫': '99%+',
}

AI_STRATEGY_PROMPT = (
    '根据考生全省位次 X，仅使用位次（不用分数）按以下区间划分冲稳保：'
    '冲刺 0.90X~0.95X（录取概率约30%-50%）；'
    '稳妥 0.95X~1.05X（录取概率约80%+）；'
    '保底 1.15X~1.25X（录取概率约98%+）。'
    '结合选科、意向专业、城市、学费，分三类列出院校并标注录取概率。'
    '高分段（全省前10%）冲刺可放宽到 0.85X~0.95X、保底 1.10X~1.18X；'
    '低分段/专科批次保底放宽到 1.25X~1.35X。'
    '各省志愿数量不同，冲稳保配额会按省规则等比放大（如河南本科批 48 组），不是固定冲3稳6保3。'
)


def is_zhuanke_batch(batch: str | None) -> bool:
    return bool(batch and '专科' in batch)


def detect_segment(user_rank: int, province_total_rank: int | None = None, batch: str = '') -> str:
    if is_zhuanke_batch(batch):
        return 'low'
    if province_total_rank and province_total_rank > 0:
        ratio = user_rank / province_total_rank
        if ratio <= 0.10:
            return 'high'
        if ratio >= 0.85:
            return 'low'
    return 'mid'


def get_band_coefficients(segment: str, batch: str = '') -> dict[str, tuple[float, float]]:
    if is_zhuanke_batch(batch):
        return {
            '冲': (0.92, 0.98),
            '稳': (0.95, 1.05),
            '保': (1.25, 1.35),
        }
    if segment == 'high':
        return {
            '冲': (0.85, 0.95),
            '稳': (0.95, 1.05),
            '保': (1.10, 1.18),
        }
    if segment == 'low':
        return {
            '冲': (0.92, 0.98),
            '稳': (0.95, 1.05),
            '保': (1.25, 1.35),
        }
    return {
        '冲': (0.90, 0.95),
        '稳': (0.95, 1.05),
        '保': (1.15, 1.25),
    }


def resolve_school_rank(item: dict[str, Any]) -> int | None:
    rank = item.get('weighted_rank')
    if rank is None:
        rank = item.get('min_rank')
    if rank is None:
        return None
    try:
        return int(rank)
    except (TypeError, ValueError):
        return None


def rank_distance(school_rank: int | None, user_rank: int) -> float:
    if school_rank is None or not user_rank or user_rank <= 0:
        return float('inf')
    return abs(float(school_rank) - float(user_rank))


def get_pool_rank_window(user_rank: int, segment: str = 'mid', batch: str = '') -> tuple[int, int]:
    if not user_rank or user_rank <= 0:
        return 1, 10_000_000
    coeffs = get_band_coefficients(segment, batch)
    lower = max(1, int(user_rank * coeffs['冲'][0] * 0.80))
    upper = int(user_rank * coeffs['保'][1] * 1.20)
    if is_zhuanke_batch(batch):
        upper = max(upper, int(user_rank * 1.50))
    return lower, upper


def get_backfill_rank_cap(user_rank: int, segment: str = 'mid', batch: str = '') -> int:
    if not user_rank or user_rank <= 0:
        return 10_000_000
    coeffs = get_band_coefficients(segment, batch)
    return int(user_rank * coeffs['保'][1] * 1.30)


def filter_rank_eligible_candidates(
    candidates: list[dict[str, Any]],
    user_rank: int,
    segment: str = 'mid',
    batch: str = '',
    *,
    min_required: int = 0,
) -> list[dict[str, Any]]:
    with_rank = [item for item in candidates if resolve_school_rank(item) is not None]
    if not user_rank or user_rank <= 0:
        return with_rank

    lower, upper = get_pool_rank_window(user_rank, segment, batch)
    filtered = [
        item for item in with_rank
        if lower <= int(resolve_school_rank(item) or 0) <= upper
    ]
    if len(filtered) >= min_required:
        return filtered

    coeffs = get_band_coefficients(segment, batch)
    widened_upper = int(user_rank * coeffs['保'][1] * 1.50)
    return [
        item for item in with_rank
        if lower <= int(resolve_school_rank(item) or 0) <= widened_upper
    ]


def classify_gradient(
    user_rank: int,
    school_rank: int | None,
    segment: str = 'mid',
    batch: str = '',
) -> str:
    if not user_rank or user_rank <= 0:
        return '稳'
    if school_rank is None:
        return '垫'

    coeffs = get_band_coefficients(segment, batch)
    rank = float(school_rank)
    x = float(user_rank)

    if coeffs['冲'][0] * x <= rank <= coeffs['冲'][1] * x:
        return '冲'
    if coeffs['稳'][0] * x <= rank <= coeffs['稳'][1] * x:
        return '稳'
    if coeffs['保'][0] * x <= rank <= coeffs['保'][1] * x:
        return '保'
    if rank < coeffs['冲'][0] * x:
        return '冲'
    if rank > coeffs['保'][1] * x:
        return '垫'
    if rank < coeffs['保'][0] * x:
        return '稳'
    return '保'


def get_plan_quotas(plan_style: str, batch: str = '', total_slots: int | None = None) -> dict[str, int]:
    if is_zhuanke_batch(batch):
        base = PLAN_STYLES_ZHUANKE.copy()
    else:
        base = PLAN_STYLES.get(plan_style, PLAN_STYLES['balanced']).copy()

    if not total_slots or total_slots <= 0:
        return base

    base_total = sum(base.values())
    if base_total == total_slots:
        return base

    scale = total_slots / base_total
    scaled = {key: max(0, int(round(count * scale))) for key, count in base.items()}
    diff = total_slots - sum(scaled.values())
    if diff > 0:
        scaled['稳'] = scaled.get('稳', 0) + diff
    elif diff < 0:
        scaled['稳'] = max(0, scaled.get('稳', 0) + diff)
    return scaled


def estimate_rank_from_score(rows: list[dict[str, Any]], score: int) -> int | None:
    candidates = [
        row for row in rows
        if row.get('min_score') is not None and row.get('min_rank') is not None
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: abs(int(item['min_score']) - int(score)))
    sample = candidates[:20]
    return int(round(sum(int(item['min_rank']) for item in sample) / len(sample)))


def build_strategy_meta(
    user_rank: int,
    segment: str,
    batch: str,
    plan_style: str,
    total_slots: int,
) -> dict[str, Any]:
    coeffs = get_band_coefficients(segment, batch)
    quotas = get_plan_quotas(plan_style, batch, total_slots)
    pool_lower, pool_upper = get_pool_rank_window(user_rank, segment, batch)
    return {
        'user_rank': user_rank,
        'segment': segment,
        'batch': batch,
        'plan_style': plan_style,
        'quotas': quotas,
        'bands': {
            'chong': [int(user_rank * coeffs['冲'][0]), int(user_rank * coeffs['冲'][1])],
            'wen': [int(user_rank * coeffs['稳'][0]), int(user_rank * coeffs['稳'][1])],
            'bao': [int(user_rank * coeffs['保'][0]), int(user_rank * coeffs['保'][1])],
        },
        'pool_rank_window': [pool_lower, pool_upper],
        'algorithm': '位次冲稳保：按全省位次 X 与分段系数划分，近三年录取位次加权，候选池先按位次窗口过滤',
        'ai_prompt_hint': AI_STRATEGY_PROMPT,
    }


def assemble_recommendation_plan(
    candidates: list[dict[str, Any]],
    user_rank: int,
    plan_style: str = 'balanced',
    batch: str = '',
    segment: str = 'mid',
    total_slots: int = 9,
    max_majors_per_school: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quotas = get_plan_quotas(plan_style, batch, total_slots)
    eligible = filter_rank_eligible_candidates(
        candidates,
        user_rank,
        segment,
        batch,
        min_required=total_slots,
    )
    backfill_cap = get_backfill_rank_cap(user_rank, segment, batch)
    buckets: dict[str, list[dict[str, Any]]] = {'冲': [], '稳': [], '保': [], '垫': []}

    for item in eligible:
        school_rank = resolve_school_rank(item)
        gradient = classify_gradient(user_rank, school_rank, segment, batch)
        enriched = {
            **item,
            'gradient_type': gradient,
            'admission_probability': ADMISSION_PROBABILITY.get(gradient, ''),
        }
        buckets[gradient].append(enriched)

    for gradient in buckets:
        buckets[gradient].sort(
            key=lambda row: rank_distance(resolve_school_rank(row), user_rank)
        )

    selected: list[dict[str, Any]] = []
    used_keys: set[tuple[Any, Any]] = set()
    school_pick_counts: dict[Any, int] = {}

    def can_pick_school(row: dict[str, Any]) -> bool:
        if not max_majors_per_school or max_majors_per_school <= 0:
            return True
        school_id = row.get('school_id')
        if school_id is None:
            return True
        return school_pick_counts.get(school_id, 0) < max_majors_per_school

    def record_pick(row: dict[str, Any]) -> None:
        school_id = row.get('school_id')
        if school_id is not None:
            school_pick_counts[school_id] = school_pick_counts.get(school_id, 0) + 1

    def pick_from_bucket(gradient: str, limit: int) -> None:
        count = 0
        for row in buckets[gradient]:
            if count >= limit:
                break
            key = (row.get('school_id'), row.get('major_id'))
            if key in used_keys or not can_pick_school(row):
                continue
            selected.append(row)
            used_keys.add(key)
            record_pick(row)
            count += 1

    for gradient in ('冲', '稳', '保'):
        pick_from_bucket(gradient, quotas.get(gradient, 0))

    if len(selected) < total_slots:
        for gradient in ('稳', '保', '垫', '冲'):
            for row in buckets[gradient]:
                if len(selected) >= total_slots:
                    break
                school_rank = resolve_school_rank(row)
                if school_rank is not None and school_rank > backfill_cap:
                    continue
                key = (row.get('school_id'), row.get('major_id'))
                if key in used_keys or not can_pick_school(row):
                    continue
                selected.append(row)
                used_keys.add(key)
                record_pick(row)

    selected.sort(
        key=lambda row: (
            {'冲': 0, '稳': 1, '保': 2, '垫': 3}.get(row.get('gradient_type', '稳'), 9),
            rank_distance(resolve_school_rank(row), user_rank),
        )
    )

    meta = build_strategy_meta(user_rank, segment, batch, plan_style, total_slots)
    meta['selected_counts'] = {
        gradient: sum(1 for row in selected if row.get('gradient_type') == gradient)
        for gradient in ('冲', '稳', '保', '垫')
    }
    meta['candidate_pool_before_filter'] = len(candidates)
    meta['candidate_pool_after_filter'] = len(eligible)
    return selected[:total_slots], meta
