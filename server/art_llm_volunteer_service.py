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
    VOLUNTEER_MODE,
    VOLUNTEER_RULE_DESCRIPTION,
    VOLUNTEER_SLOTS,
    _art_sports_risk_reason,
    _classify_tier,
    _infer_exam_type,
    assemble_art_sports_parallel_plan,
    calculate_composite,
    category_from_exam_type,
    get_art_sports_quotas,
    request_to_match_payload,
    resolve_school_major_ids,
)

CACHE_TTL_DAYS = 7
ADMISSION_FETCH_MAX_TOKENS = 4096
PLAN_GENERATION_MAX_TOKENS = 8192


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
    return [_normalize_admission_row(item) for item in admissions if _normalize_admission_row(item)]


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


def _normalize_admission_row(row: dict[str, Any]) -> dict[str, Any] | None:
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
        'data_source': 'llm_art_2025',
    }


def build_admission_fetch_prompt(batch: str, formula_id: int, formula_label: str) -> str:
    return f'''请整理河南省「{batch}」2025年艺术类院校专业在河南省招生的最低综合分参考线（投档/录取最低综合分）。
综合分公式参照：{formula_label}（公式编号 {formula_id}）

要求：
1. 覆盖省内外在河南招生的主要艺术类院校及专业，本科层次为主
2. 每条包含 school_name、major_name、min_composite_2025（数字）、city（城市，可空）
3. 至少返回 100 条，分数合理分布在 350~580 之间
4. 基于2025年河南艺术类招生实际情况；不确定的院校可合理估算
5. 只输出 JSON，格式如下：
{{"admissions":[{{"school_name":"郑州大学","major_name":"音乐表演","min_composite_2025":512.5,"city":"郑州"}}]}}'''


def collect_art_2025_admissions_via_llm(batch: str, formula_id: int, formula_label: str) -> list[dict[str, Any]]:
    cached = load_cached_admissions(batch, formula_id)
    if cached:
        return cached

    content = chat_completion(
        [
            {
                'role': 'system',
                'content': (
                    '你是河南省高考艺术类招生数据专家，熟悉2025年各院校在河南艺术批次的录取情况。'
                    '你必须只输出合法 JSON，不要输出 markdown 代码块或额外说明。'
                ),
            },
            {'role': 'user', 'content': build_admission_fetch_prompt(batch, formula_id, formula_label)},
        ],
        max_tokens=ADMISSION_FETCH_MAX_TOKENS,
    )
    payload = extract_json_payload(content)
    admissions = payload.get('admissions') if isinstance(payload, dict) else payload
    if not isinstance(admissions, list):
        raise ValueError('大模型未返回 admissions 列表')
    normalized = [_normalize_admission_row(item) for item in admissions]
    normalized = [item for item in normalized if item]
    if len(normalized) < 20:
        raise ValueError(f'大模型返回的2025录取线过少（{len(normalized)}条）')
    save_cached_admissions(batch, formula_id, normalized, source_note='llm_fetch_2025')
    return normalized


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
) -> str:
    sample_lines = []
    for item in admissions[:120]:
        sample_lines.append(
            f"- {item['school_name']} / {item['major_name']} / 2025最低综合分 {item['min_composite_2025']}"
        )
    quotas = {'balanced': '冲16 稳24 保24', 'aggressive': '冲24 稳24 保16', 'conservative': '冲12 稳20 保32'}
    quota_text = quotas.get(plan_style, quotas['balanced'])
    return f'''请为河南省艺术类考生生成「{batch}」64个「专业+院校」平行志愿方案。

学生信息：
- 省份：河南
- 批次：{batch}
- 选科：{subject_combination or '未填'}
- 文化课分数 W：{culture_score}
- 专业统考分 Z：{professional_score}
- 综合分公式：{formula_label}
- 考生综合分：{composite_score}
- 方案风格：{plan_style}（{quota_text}）

河南省无艺体综合分官方位次，请用2025年院校在河南艺术批的最低综合分对标匹配。
已采集的2025录取线参考（节选）：
{chr(10).join(sample_lines)}

生成规则：
1. 必须输出恰好 64 条志愿，sort_order 从 1 到 64
2. 前段冲、中段稳、后段保；同档按 min_composite_2025 从高到低
3. 每条含：sort_order, gradient_type（冲/稳/保）, school_name, major_name, min_composite_2025, city
4. min_composite_2025 须来自上述参考或同类院校合理推断
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
        'data_source': 'llm_art_2025',
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
    content = chat_completion(
        [
            {
                'role': 'system',
                'content': (
                    '你是河南省高考艺术类志愿填报专家。'
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
                    admissions=admissions,
                    subject_combination=subject_combination,
                ),
            },
        ],
        max_tokens=PLAN_GENERATION_MAX_TOKENS,
    )
    payload = extract_json_payload(content)
    volunteers = payload.get('volunteers') if isinstance(payload, dict) else payload
    if not isinstance(volunteers, list):
        raise ValueError('大模型未返回 volunteers 列表')

    seen: set[tuple[str, str]] = set()
    items: list[dict[str, Any]] = []
    for row in volunteers:
        if not isinstance(row, dict):
            continue
        school_name = str(row.get('school_name') or '').strip()
        major_name = str(row.get('major_name') or '').strip()
        key = (school_name, major_name)
        if not school_name or not major_name or key in seen:
            continue
        seen.add(key)
        items.append(
            _volunteer_row_to_plan_item(
                row,
                composite_score=composite_score,
                accept_adjustment=accept_adjustment,
                formula_id=formula_id,
                category=category,
            )
        )

    if len(items) < VOLUNTEER_SLOTS:
        local_items = _local_plan_from_admissions(
            admissions,
            composite_score=composite_score,
            plan_style=plan_style,
            accept_adjustment=accept_adjustment,
            formula_id=formula_id,
            category=category,
        )
        for item in local_items:
            key = (item['school_name'], item['major_name'])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= VOLUNTEER_SLOTS:
                break

    items = items[:VOLUNTEER_SLOTS]
    for index, item in enumerate(items, start=1):
        item['sort_order'] = index
    if len(items) < 8:
        raise ValueError(f'大模型志愿方案不足（{len(items)}条）')
    return items


def build_art_llm_recommendation(data: dict[str, Any]) -> dict[str, Any]:
    if not is_llm_available():
        raise ValueError('大模型未启用，无法生成艺术类志愿')

    payload = request_to_match_payload(data)
    calc = calculate_composite({**payload, 'category': payload['category']})
    if calc.get('use_normal_track'):
        raise ValueError('已放弃艺体批次，请使用普通类志愿检索')

    batch = str(data.get('batch') or '艺术本科批')
    plan_style = data.get('plan_style') or 'balanced'
    formula_id = int(calc['formula_id'])
    formula_label = ART_FORMULA_LABELS.get(formula_id, '')
    composite_score = float(calc['composite_score'])
    culture_score = float(payload['culture_score'])
    professional_score = float(payload['professional_score'])
    accept_adjustment = bool(data.get('accept_adjustment', True))
    subject_combination = str(data.get('subject_combination') or '')

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
                'rank_notice': '河南省不发布艺体综合分官方位次；艺术类志愿由大模型采集2025录取线对标生成。',
                'data_source': 'llm_art_2025',
                'generation_mode': 'llm',
            },
            'generation': {'target_slots': VOLUNTEER_SLOTS, 'generated_count': 0, 'candidate_pool': 0},
            'art_sports_mode': True,
        }

    admissions = collect_art_2025_admissions_via_llm(batch, formula_id, formula_label)
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
        category=payload['category'],
    )

    quotas = get_art_sports_quotas(plan_style)
    warnings: list[str] = []
    if len(selected) < VOLUNTEER_SLOTS:
        warnings.append(f'大模型生成 {len(selected)}/{VOLUNTEER_SLOTS} 个志愿，候选录取线 {len(admissions)} 条。')
    warnings.append('志愿方案由大模型基于2025年河南艺术录取线生成，仅供参考，请以考试院和高校招生章程为准。')

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
            'message': '大模型已采集2025年河南艺术录取最低综合分，并按考生综合分匹配生成64个平行志愿（非官方位次）。',
            'volunteer_slots': VOLUNTEER_SLOTS,
            'rank_notice': '河南省不发布艺体综合分官方位次；艺术类志愿由大模型采集2025录取线对标生成。',
            'data_source': 'llm_art_2025',
            'candidate_count': len(admissions),
            'generation_mode': 'llm',
            'volunteer_rule': {
                'total_slots': VOLUNTEER_SLOTS,
                'school_count': VOLUNTEER_SLOTS,
                'batch': batch,
                'volunteer_mode': VOLUNTEER_MODE,
                'matched': True,
                'source': 'llm_art_2025',
                'rule_description': VOLUNTEER_RULE_DESCRIPTION,
            },
            'quotas': quotas,
            'parallel_layout': '平行志愿按志愿序号有序排布：前段冲、中段稳、后段保（大模型基于2025录取线匹配）。',
        },
        'generation': {
            'target_slots': VOLUNTEER_SLOTS,
            'generated_count': len(selected),
            'candidate_pool': len(admissions),
            'generation_mode': 'llm',
        },
        'art_sports_mode': True,
    }


def try_build_art_llm_recommendation(data: dict[str, Any]) -> dict[str, Any] | None:
    if _infer_exam_type(data) != '艺术类':
        return None
    if not is_llm_available():
        return None
    try:
        return build_art_llm_recommendation(data)
    except Exception:
        return None
