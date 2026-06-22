"""河南省艺术类志愿：大模型采集2025录取线并生成64个平行志愿。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from db import get_connection
from llm_settings_service import chat_completion, get_llm_settings

from henan_art_sports_service import (
    ART_FORMULA_LABELS,
    PROVINCE,
    SPORTS_FORMULA_LABELS,
    VOLUNTEER_MODE,
    VOLUNTEER_RULE_DESCRIPTION,
    VOLUNTEER_SLOTS,
    _art_sports_risk_reason,
    _classify_tier,
    _infer_exam_type,
    assemble_art_sports_parallel_plan,
    batch_level_from_target_batch,
    calculate_composite,
    category_from_exam_type,
    expand_art_sports_admissions,
    get_art_sports_quotas,
    request_to_match_payload,
    resolve_school_major_ids,
)

CACHE_TTL_DAYS = 7
ADMISSION_FETCH_MAX_TOKENS = 4096
PLAN_GENERATION_MAX_TOKENS = 8192
ADMISSION_FETCH_TIMEOUT = 90
PLAN_GENERATION_TIMEOUT = 120


def ensure_art_llm_cache_table() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS art_llm_admission_cache (
              cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
              province TEXT NOT NULL,
              batch TEXT NOT NULL,
              formula_id INTEGER NOT NULL,
              admissions_json TEXT NOT NULL,
              source_note TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              expires_at TEXT NOT NULL,
              UNIQUE (province, batch, formula_id)
            )
            '''
        )
        connection.commit()


def is_llm_available() -> bool:
    settings = get_llm_settings()
    return bool(settings and settings.get('is_enabled') and settings.get('api_key') and settings.get('model_name'))


def extract_json_payload(text: str) -> Any:
    cleaned = str(text or '').strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]
    return json.loads(cleaned)


def _cache_key(batch: str, formula_id: int) -> tuple[str, str, int]:
    return PROVINCE, batch, int(formula_id)


def _category_from_batch(batch: str) -> str:
    return '体育类' if '体育' in str(batch or '') else '艺术类'


def load_cached_admissions(batch: str, formula_id: int) -> list[dict[str, Any]] | None:
    ensure_art_llm_cache_table()
    with get_connection() as connection:
        row = connection.execute(
            '''
            SELECT admissions_json, expires_at FROM art_llm_admission_cache
            WHERE province = ? AND batch = ? AND formula_id = ?
            ''',
            list(_cache_key(batch, formula_id)),
        ).fetchone()
    if not row:
        return None
    expires_at = row['expires_at']
    if expires_at and expires_at < datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'):
        return None
    try:
        payload = json.loads(row['admissions_json'])
    except json.JSONDecodeError:
        return None
    admissions = payload.get('admissions') if isinstance(payload, dict) else payload
    if not isinstance(admissions, list) or not admissions:
        return None
    return [_normalize_admission_row(item, _category_from_batch(batch)) for item in admissions if _normalize_admission_row(item, _category_from_batch(batch))]


def save_cached_admissions(
    batch: str,
    formula_id: int,
    admissions: list[dict[str, Any]],
    *,
    source_note: str = '',
) -> None:
    ensure_art_llm_cache_table()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=CACHE_TTL_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO art_llm_admission_cache (province, batch, formula_id, admissions_json, source_note, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(province, batch, formula_id) DO UPDATE SET
              admissions_json = excluded.admissions_json,
              source_note = excluded.source_note,
              expires_at = excluded.expires_at,
              created_at = CURRENT_TIMESTAMP
            ''',
            [
                PROVINCE,
                batch,
                int(formula_id),
                json.dumps({'admissions': admissions}, ensure_ascii=False),
                source_note,
                expires_at,
            ],
        )
        connection.commit()


def _normalize_admission_row(row: dict[str, Any], category: str = '艺术类') -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    school_name = str(row.get('school_name') or row.get('schoolName') or '').strip()
    major_name = str(row.get('major_name') or row.get('majorName') or '').strip()
    if not school_name or not major_name:
        return None
    score = row.get('min_composite_2025')
    if score in (None, ''):
        score = row.get('ref_min_composite') or row.get('min_score')
    try:
        min_composite_2025 = round(float(score), 2)
    except (TypeError, ValueError):
        return None
    return {
        'school_name': school_name,
        'major_name': major_name,
        'min_composite_2025': min_composite_2025,
        'ref_min_composite': min_composite_2025,
        'city': str(row.get('city') or '').strip(),
        'data_source': _llm_data_source(category),
    }


def _formula_labels(category: str) -> dict[int, str]:
    return ART_FORMULA_LABELS if category == '艺术类' else SPORTS_FORMULA_LABELS


def _llm_data_source(category: str) -> str:
    return 'llm_art_2025' if category == '艺术类' else 'llm_sports_2025'


def build_admission_fetch_prompt(batch: str, formula_id: int, formula_label: str, category: str = '艺术类') -> str:
    subject_label = '艺术类' if category == '艺术类' else '体育类'
    score_range = '350~580' if category == '艺术类' else '500~700'
    data_hint = (
        '请结合河南省教育考试院、阳光高考网、各高校2025年招生章程等公开信息'
        '检索整理2025年在河南招生的最低投档/录取综合分。'
    )
    return f'''请整理河南省「{batch}」2025年{subject_label}院校专业在河南省招生的最低综合分参考线（投档/录取最低综合分）。
综合分公式参照：{formula_label}（公式编号 {formula_id}）

要求：
1. {data_hint}
2. 覆盖省内外在河南招生的主要{subject_label}院校及专业，本科层次为主
3. 每条包含 school_name、major_name、min_composite_2025（数字）、city（城市，可空）
4. 至少返回 120 条，分数合理分布在 {score_range} 之间
5. 河南省不发布艺体综合分官方位次，请用最低综合分对标，不要编造位次
6. 只输出 JSON，格式如下：
{{"admissions":[{{"school_name":"郑州大学","major_name":"音乐表演","min_composite_2025":512.5,"city":"郑州"}}]}}'''


def collect_art_sports_2025_admissions_via_llm(
    batch: str,
    formula_id: int,
    formula_label: str,
    category: str = '艺术类',
    *,
    composite_score: float | None = None,
) -> list[dict[str, Any]]:
    cached = load_cached_admissions(batch, formula_id)
    if cached:
        return expand_art_sports_admissions(
            cached,
            category=category,
            batch_level='专科' if '专科' in batch else '本科',
            formula_id=int(formula_id),
            composite_score=float(composite_score or 500.0),
            minimum=max(128, VOLUNTEER_SLOTS + 16),
        )

    subject_label = '艺术类' if category == '艺术类' else '体育类'
    content = chat_completion(
        [
            {
                'role': 'system',
                'content': (
                    f'你是河南省高考{subject_label}招生数据专家，熟悉2025年各院校在河南{subject_label}批次的录取情况。'
                    '你必须只输出合法 JSON，不要输出 markdown 代码块或额外说明。'
                ),
            },
            {'role': 'user', 'content': build_admission_fetch_prompt(batch, formula_id, formula_label, category)},
        ],
        max_tokens=ADMISSION_FETCH_MAX_TOKENS,
        timeout=ADMISSION_FETCH_TIMEOUT,
    )
    payload = extract_json_payload(content)
    admissions = payload.get('admissions') if isinstance(payload, dict) else payload
    if not isinstance(admissions, list):
        raise ValueError('大模型未返回 admissions 列表')
    normalized = [_normalize_admission_row(item, category) for item in admissions]
    normalized = [item for item in normalized if item]
    if len(normalized) < 20:
        raise ValueError(f'大模型返回的2025录取线过少（{len(normalized)}条）')
    expanded = expand_art_sports_admissions(
        normalized,
        category=category,
        batch_level='专科' if '专科' in batch else '本科',
        formula_id=int(formula_id),
        composite_score=float(composite_score or 500.0),
        minimum=max(128, VOLUNTEER_SLOTS + 16),
    )
    save_cached_admissions(batch, formula_id, expanded, source_note=f'llm_fetch_2025_{category}')
    return expanded


def collect_art_2025_admissions_via_llm(batch: str, formula_id: int, formula_label: str) -> list[dict[str, Any]]:
    return collect_art_sports_2025_admissions_via_llm(batch, formula_id, formula_label, '艺术类')


def build_volunteer_plan_prompt(
    *,
    batch: str,
    composite_score: float,
    culture_score: float,
    professional_score: float,
    formula_label: str,
    plan_style: str,
    admissions: list[dict[str, Any]],
    subject_combination: str = '',
    category: str = '艺术类',
) -> str:
    sample_lines = []
    for item in admissions[:120]:
        sample_lines.append(
            f"- {item['school_name']} / {item['major_name']} / 2025最低综合分 {item['min_composite_2025']}"
        )
    quotas = {'balanced': '冲16 稳24 保24', 'aggressive': '冲24 稳24 保16', 'conservative': '冲12 稳20 保32'}
    quota_text = quotas.get(plan_style, quotas['balanced'])
    pro_label = '专业统考分 Z' if category == '艺术类' else '专业统考分 T'
    return f'''请为河南省{category}考生生成「{batch}」64个「专业+院校」平行志愿方案。

学生信息：
- 省份：河南
- 类别：{category}
- 批次：{batch}
- 选科：{subject_combination or '未填'}
- 文化课分数 W：{culture_score}
- {pro_label}：{professional_score}
- 综合分公式：{formula_label}
- 考生综合分：{composite_score}
- 方案风格：{plan_style}（{quota_text}）

河南省无艺体综合分官方位次，请用2025年院校在河南对应批次的最低综合分对标匹配（不要用位次）。
已采集的2025录取线参考（节选）：
{chr(10).join(sample_lines)}

生成规则：
1. 必须输出恰好 64 条志愿，sort_order 从 1 到 64
2. 前段冲、中段稳、后段保；同档按 min_composite_2025 从高到低
3. 每条含：sort_order, gradient_type（冲/稳/保）, school_name, major_name, min_composite_2025, city
4. min_composite_2025 须来自上述参考或同类院校合理推断，并作为2025年在河南录取最低综合分展示
5. 院校+专业不可重复
6. 只输出 JSON：
{{"volunteers":[{{"sort_order":1,"gradient_type":"冲","school_name":"","major_name":"","min_composite_2025":0,"city":""}}]}}'''


def _volunteer_row_to_plan_item(
    row: dict[str, Any],
    *,
    composite_score: float,
    accept_adjustment: bool,
    formula_id: int,
    category: str,
) -> dict[str, Any]:
    school_name = str(row.get('school_name') or '').strip()
    major_name = str(row.get('major_name') or '').strip()
    ref = float(row.get('min_composite_2025') or row.get('ref_min_composite') or 0)
    diff = round(composite_score - ref, 2)
    gradient = row.get('gradient_type')
    if gradient in ('冲刺', 'rush'):
        gradient = '冲'
    elif gradient in ('稳妥', 'steady'):
        gradient = '稳'
    elif gradient in ('保底', 'safe'):
        gradient = '保'
    if gradient not in ('冲', '稳', '保'):
        tier, _ = _classify_tier(diff)
        gradient = {'rush': '冲', 'steady': '稳', 'safe': '保'}[tier]
    school_id, major_id = resolve_school_major_ids(school_name, major_name, category)
    return {
        'sort_order': int(row.get('sort_order') or 0),
        'gradient_type': gradient,
        'school_id': school_id,
        'school_name': school_name,
        'school_code': row.get('school_code') or '',
        'major_id': major_id,
        'major_name': major_name,
        'major_code': row.get('major_code') or '',
        'major_type': category,
        'city': row.get('city') or '',
        'school_type': row.get('school_type') or '',
        'tuition': row.get('tuition'),
        'duration': row.get('duration'),
        'min_score': ref,
        'min_rank': None,
        'weighted_score': ref,
        'weighted_rank': None,
        'years_used': [2025],
        'admission_probability': f'综合分分差 {diff}',
        'preference_score': 0,
        'personality_matched': False,
        'is_adjustable': accept_adjustment,
        'risk_level': '低' if gradient == '保' else ('中' if gradient == '稳' else '高'),
        'risk_reason': _art_sports_risk_reason(gradient, accept_adjustment, ref),
        'ref_min_composite': ref,
        'min_composite_2025': ref,
        'score_diff': diff,
        'formula_id': formula_id,
        'art_sports_mode': True,
        'data_source': _llm_data_source(category) if category else 'llm_art_2025',
    }


def _local_plan_from_admissions(
    admissions: list[dict[str, Any]],
    *,
    composite_score: float,
    plan_style: str,
    accept_adjustment: bool,
    formula_id: int,
    category: str,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for school in admissions:
        ref = float(school.get('min_composite_2025') or school.get('ref_min_composite') or 0)
        diff = composite_score - ref
        tier, _ = _classify_tier(diff)
        gradient = {'rush': '冲', 'steady': '稳', 'safe': '保'}[tier]
        ranked.append({
            **school,
            'ref_min_composite': ref,
            'score_diff': round(diff, 2),
            'gradient_type': gradient,
        })
    ranked.sort(key=lambda item: (-(item.get('ref_min_composite') or 0), -(item.get('score_diff') or 0)))
    pool = [
        _volunteer_row_to_plan_item(
            item,
            composite_score=composite_score,
            accept_adjustment=accept_adjustment,
            formula_id=formula_id,
            category=category,
        )
        for item in ranked
    ]
    return assemble_art_sports_parallel_plan(pool, plan_style)


def _merge_llm_and_local_plans(
    llm_items: list[dict[str, Any]],
    local_items: list[dict[str, Any]],
    *,
    total_slots: int = VOLUNTEER_SLOTS,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in llm_items:
        key = (item['school_name'], item['major_name'])
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= total_slots:
            break
    for item in local_items:
        key = (item['school_name'], item['major_name'])
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= total_slots:
            break
    for index, item in enumerate(selected[:total_slots], start=1):
        item['sort_order'] = index
    return selected[:total_slots]


def generate_art_volunteer_plan_via_llm(
    *,
    batch: str,
    composite_score: float,
    culture_score: float,
    professional_score: float,
    formula_id: int,
    formula_label: str,
    plan_style: str,
    admissions: list[dict[str, Any]],
    subject_combination: str = '',
    accept_adjustment: bool = True,
    category: str = '艺术类',
) -> list[dict[str, Any]]:
    batch_level = batch_level_from_target_batch(batch)
    expanded = expand_art_sports_admissions(
        admissions,
        category=category,
        batch_level=batch_level,
        formula_id=formula_id,
        composite_score=composite_score,
        minimum=max(128, VOLUNTEER_SLOTS + 16),
    )
    local_items = _local_plan_from_admissions(
        expanded,
        composite_score=composite_score,
        plan_style=plan_style,
        accept_adjustment=accept_adjustment,
        formula_id=formula_id,
        category=category,
    )

    llm_items: list[dict[str, Any]] = []
    try:
        subject_label = '艺术类' if category == '艺术类' else '体育类'
        content = chat_completion(
            [
                {
                    'role': 'system',
                    'content': (
                        f'你是河南省高考{subject_label}志愿填报专家。'
                        '你必须只输出合法 JSON，不要输出 markdown 代码块或额外说明。'
                    ),
                },
                {
                    'role': 'user',
                    'content': build_volunteer_plan_prompt(
                        batch=batch,
                        composite_score=composite_score,
                        culture_score=culture_score,
                        professional_score=professional_score,
                        formula_label=formula_label,
                        plan_style=plan_style,
                        admissions=expanded,
                        subject_combination=subject_combination,
                        category=category,
                    ),
                },
            ],
            max_tokens=PLAN_GENERATION_MAX_TOKENS,
            timeout=PLAN_GENERATION_TIMEOUT,
        )
        payload = extract_json_payload(content)
        volunteers = payload.get('volunteers') if isinstance(payload, dict) else payload
        if isinstance(volunteers, list):
            seen: set[tuple[str, str]] = set()
            for row in volunteers:
                if not isinstance(row, dict):
                    continue
                school_name = str(row.get('school_name') or '').strip()
                major_name = str(row.get('major_name') or '').strip()
                key = (school_name, major_name)
                if not school_name or not major_name or key in seen:
                    continue
                seen.add(key)
                llm_items.append(
                    _volunteer_row_to_plan_item(
                        row,
                        composite_score=composite_score,
                        accept_adjustment=accept_adjustment,
                        formula_id=formula_id,
                        category=category,
                    )
                )
    except Exception:
        llm_items = []

    items = _merge_llm_and_local_plans(llm_items, local_items)
    if len(items) < VOLUNTEER_SLOTS:
        items = local_items[:VOLUNTEER_SLOTS]
    if len(items) < VOLUNTEER_SLOTS:
        raise ValueError(
            f'无法凑满 {VOLUNTEER_SLOTS} 个志愿（当前 {len(items)} 个，候选池 {len(expanded)} 条）'
        )
    for index, item in enumerate(items[:VOLUNTEER_SLOTS], start=1):
        item['sort_order'] = index
    return items[:VOLUNTEER_SLOTS]


def build_art_sports_llm_recommendation(data: dict[str, Any]) -> dict[str, Any]:
    if not is_llm_available():
        raise ValueError('大模型未启用，请在管理后台「大模型设置」中启用并配置 API Key')

    payload = request_to_match_payload(data)
    category = payload['category']
    calc = calculate_composite({**payload, 'category': category})
    if calc.get('use_normal_track'):
        raise ValueError('已放弃艺体批次，请使用普通类志愿检索')

    exam_type = _infer_exam_type(data)
    default_batch = '艺术本科批' if exam_type == '艺术类' else '体育本科批'
    batch = str(data.get('batch') or default_batch)
    plan_style = data.get('plan_style') or 'balanced'
    formula_id = int(calc['formula_id'])
    formula_label = _formula_labels(category).get(formula_id, '')
    composite_score = float(calc['composite_score'])
    culture_score = float(payload['culture_score'])
    professional_score = float(payload['professional_score'])
    accept_adjustment = bool(data.get('accept_adjustment', True))
    subject_combination = str(data.get('subject_combination') or '')
    data_source = _llm_data_source(category)
    subject_text = '艺术' if category == '艺术类' else '体育'

    if payload['batch_level'] == '本科' and not calc['dual_line'].get('dual_line_ok'):
        return {
            'items': [],
            'risk': {'level': '高', 'count': {}, 'warnings': ['未满足双过线，本科院校推荐已屏蔽；可填专科或勾选放弃艺体批次走普通类。']},
            'strategy': {
                'mode': 'art_llm_composite',
                'composite_score': composite_score,
                'formula_label': formula_label,
                'dual_line': calc['dual_line'],
                'eligible': False,
                'message': '未满足双过线，本科院校推荐已屏蔽。',
                'volunteer_slots': VOLUNTEER_SLOTS,
                'rank_notice': f'河南省不发布艺体综合分官方位次；{category}志愿由大模型采集2025录取线对标生成。',
                'data_source': data_source,
                'generation_mode': 'llm',
            },
            'generation': {'target_slots': VOLUNTEER_SLOTS, 'generated_count': 0, 'candidate_pool': 0, 'generation_mode': 'llm'},
            'art_sports_mode': True,
        }

    admissions = collect_art_sports_2025_admissions_via_llm(
        batch, formula_id, formula_label, category, composite_score=composite_score,
    )
    expanded_count = len(admissions)
    selected = generate_art_volunteer_plan_via_llm(
        batch=batch,
        composite_score=composite_score,
        culture_score=culture_score,
        professional_score=professional_score,
        formula_id=formula_id,
        formula_label=formula_label,
        plan_style=plan_style,
        admissions=admissions,
        subject_combination=subject_combination,
        accept_adjustment=accept_adjustment,
        category=category,
    )

    quotas = get_art_sports_quotas(plan_style)
    warnings: list[str] = []
    if len(selected) < VOLUNTEER_SLOTS:
        warnings.append(f'志愿生成 {len(selected)}/{VOLUNTEER_SLOTS} 个，候选录取线 {expanded_count} 条。')
    warnings.append(
        f'志愿方案由大模型基于2025年河南{subject_text}录取最低综合分生成，仅供参考，请以考试院和高校招生章程为准。'
    )

    return {
        'items': selected,
        'risk': {
            'level': '低' if selected else '高',
            'count': {
                '冲': sum(1 for x in selected if x.get('gradient_type') == '冲'),
                '稳': sum(1 for x in selected if x.get('gradient_type') == '稳'),
                '保': sum(1 for x in selected if x.get('gradient_type') == '保'),
            },
            'warnings': warnings,
        },
        'strategy': {
            'mode': 'art_llm_composite',
            'composite_score': composite_score,
            'formula_label': formula_label,
            'dual_line': calc['dual_line'],
            'eligible': True,
            'message': f'大模型已采集2025年河南{subject_text}录取最低综合分，并按考生综合分匹配生成64个平行志愿（非官方位次）。',
            'volunteer_slots': VOLUNTEER_SLOTS,
            'rank_notice': f'河南省不发布艺体综合分官方位次；{category}志愿由大模型采集2025录取线对标生成。',
            'data_source': data_source,
            'candidate_count': expanded_count,
            'generation_mode': 'llm',
            'volunteer_rule': {
                'total_slots': VOLUNTEER_SLOTS,
                'school_count': VOLUNTEER_SLOTS,
                'batch': batch,
                'volunteer_mode': VOLUNTEER_MODE,
                'matched': True,
                'source': data_source,
                'rule_description': VOLUNTEER_RULE_DESCRIPTION,
            },
            'quotas': quotas,
            'parallel_layout': '平行志愿按志愿序号有序排布：前段冲、中段稳、后段保（大模型基于2025录取线匹配）。',
        },
        'generation': {
            'target_slots': VOLUNTEER_SLOTS,
            'generated_count': len(selected),
            'candidate_pool': expanded_count,
            'generation_mode': 'llm',
        },
        'art_sports_mode': True,
    }


def build_art_llm_recommendation(data: dict[str, Any]) -> dict[str, Any]:
    return build_art_sports_llm_recommendation(data)


def try_build_art_sports_llm_recommendation(data: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    exam_type = _infer_exam_type(data)
    if exam_type not in ('艺术类', '体育类'):
        return None, None
    if not is_llm_available():
        return None, '大模型未启用或未配置 API Key。请管理员在后台「大模型设置」中启用后再生成艺体志愿。'
    try:
        return build_art_sports_llm_recommendation(data), None
    except Exception as exc:
        return None, f'大模型生成志愿失败：{exc}'


def try_build_art_llm_recommendation(data: dict[str, Any]) -> dict[str, Any] | None:
    plan, _error = try_build_art_sports_llm_recommendation(data)
    return plan
