"""河南艺术类 / 体育类志愿填报规则与综合分计算（小程序直接复用）。"""
from __future__ import annotations

from typing import Any, Callable

from db import get_connection

PROVINCE = '河南'
ART_PRO_MAX = 300
SPORTS_PRO_MAX = 150
VOLUNTEER_SLOTS = 64

ART_FORMULA_LABELS: dict[int, str] = {
    1: '仅文化：综合分=W',
    2: '文化80%+专业20%：综合分=0.8W+0.5Z',
    3: '文化70%+专业30%：综合分=0.7W+0.75Z',
    4: '文化60%+专业40%：综合分=0.6W+Z',
    5: '文化50%+专业50%（艺术本科默认）：综合分=0.5W+1.25Z',
}

SPORTS_FORMULA_LABELS: dict[int, str] = {
    1: '仅文化：综合分=W',
    2: '文化30%+专业70%：综合分=0.3W+3.5T',
    3: '文化50%+专业50%（体育本科默认）：综合分=0.5W+2.5T',
    4: '文化70%+专业30%：综合分=0.7W+1.5T',
    5: '仅专业：综合分=5T',
}

ART_TARGET_BATCHES = ['艺术本科批', '艺术专科批']
SPORTS_TARGET_BATCHES = ['体育本科批', '体育专科批']

# 示例院校历年最低综合分（分），实际应由后台导入维护
SAMPLE_SCHOOLS: list[dict[str, Any]] = [
    {'school_name': '郑州大学', 'major_name': '音乐表演', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 5, 'min_composite_2025': 512.5, 'min_composite_2024': 508.0, 'min_composite_2023': 505.2},
    {'school_name': '河南大学', 'major_name': '美术学', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 5, 'min_composite_2025': 498.0, 'min_composite_2024': 492.5, 'min_composite_2023': 488.0},
    {'school_name': '河南师范大学', 'major_name': '舞蹈学', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 4, 'min_composite_2025': 485.0, 'min_composite_2024': 480.0, 'min_composite_2023': 476.5},
    {'school_name': '洛阳师范学院', 'major_name': '视觉传达设计', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 5, 'min_composite_2025': 472.0, 'min_composite_2024': 468.0, 'min_composite_2023': 465.0},
    {'school_name': '郑州师范学院', 'major_name': '音乐教育', 'category': '艺术类', 'batch_level': '专科', 'formula_id': 5, 'min_composite_2025': 420.0, 'min_composite_2024': 415.0, 'min_composite_2023': 410.0},
    {'school_name': '河南体育学院', 'major_name': '社会体育指导', 'category': '体育类', 'batch_level': '本科', 'formula_id': 3, 'min_composite_2025': 628.0, 'min_composite_2024': 622.0, 'min_composite_2023': 618.5},
    {'school_name': '郑州大学', 'major_name': '体育教育', 'category': '体育类', 'batch_level': '本科', 'formula_id': 3, 'min_composite_2025': 645.0, 'min_composite_2024': 638.0, 'min_composite_2023': 632.0},
    {'school_name': '河南大学', 'major_name': '运动训练', 'category': '体育类', 'batch_level': '本科', 'formula_id': 2, 'min_composite_2025': 610.0, 'min_composite_2024': 605.0, 'min_composite_2023': 600.0},
    {'school_name': '商丘师范学院', 'major_name': '体育教育', 'category': '体育类', 'batch_level': '专科', 'formula_id': 3, 'min_composite_2025': 580.0, 'min_composite_2024': 575.0, 'min_composite_2023': 570.0},
]

RHYME = '艺体先报二选一，双线过线才投档；统考分值基数定，五套公式院校选；平行投档同普通，同分先比专业分；无官方综合位次，历年最低分对标选。'


def ensure_student_art_sports_columns() -> None:
    with get_connection() as connection:
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(students)').fetchall()}
        migrations = {
            'professional_score': 'ALTER TABLE students ADD COLUMN professional_score REAL',
            'art_sports_formula_id': 'ALTER TABLE students ADD COLUMN art_sports_formula_id INTEGER',
            'waive_art_sports_batch': 'ALTER TABLE students ADD COLUMN waive_art_sports_batch INTEGER NOT NULL DEFAULT 0',
            'culture_cutoff': 'ALTER TABLE students ADD COLUMN culture_cutoff INTEGER',
            'pro_cutoff': 'ALTER TABLE students ADD COLUMN pro_cutoff INTEGER',
        }
        for name, sql in migrations.items():
            if name not in columns:
                connection.execute(sql)
        connection.commit()


def calc_art_composite(culture_score: float, pro_score: float, formula_id: int) -> float:
    w, z = float(culture_score), float(pro_score)
    formulas: dict[int, Callable[[float, float], float]] = {
        1: lambda a, b: a,
        2: lambda a, b: 0.8 * a + 0.5 * b,
        3: lambda a, b: 0.7 * a + 0.75 * b,
        4: lambda a, b: 0.6 * a + b,
        5: lambda a, b: 0.5 * a + 1.25 * b,
    }
    if formula_id not in formulas:
        raise ValueError('艺术类公式编号须为 1~5')
    return round(formulas[formula_id](w, z), 2)


def calc_sports_composite(culture_score: float, pro_score: float, formula_id: int) -> float:
    w, t = float(culture_score), float(pro_score)
    formulas: dict[int, Callable[[float, float], float]] = {
        1: lambda a, b: a,
        2: lambda a, b: 0.3 * a + 3.5 * b,
        3: lambda a, b: 0.5 * a + 2.5 * b,
        4: lambda a, b: 0.7 * a + 1.5 * b,
        5: lambda a, b: 5 * b,
    }
    if formula_id not in formulas:
        raise ValueError('体育类公式编号须为 1~5')
    return round(formulas[formula_id](w, t), 2)


def default_formula_id(category: str, batch_level: str) -> int:
    if category == '艺术类':
        return 5
    if category == '体育类':
        return 3
    raise ValueError('类别须为艺术类或体育类')


def check_dual_line(
    culture_score: float,
    pro_score: float,
    culture_cutoff: float | None,
    pro_cutoff: float | None,
    category: str,
) -> dict[str, Any]:
    pro_max = ART_PRO_MAX if category == '艺术类' else SPORTS_PRO_MAX
    culture_ok = culture_cutoff is None or culture_score >= culture_cutoff
    pro_ok = pro_cutoff is None or pro_score >= pro_cutoff
    return {
        'culture_ok': culture_ok,
        'pro_ok': pro_ok,
        'dual_line_ok': culture_ok and pro_ok,
        'pro_max': pro_max,
        'message': (
            '双过线满足，可参与对应本科投档'
            if culture_ok and pro_ok
            else '未满足双过线：' + ('文化课未过线；' if not culture_ok else '') + ('专业未过线；' if not pro_ok else '')
        ),
    }


def get_meta() -> dict[str, Any]:
    return {
        'province': PROVINCE,
        'mutex_rule': '高考报名时艺术类/体育类二选一，不可同时报考两类统考提前批；均可放弃专业志愿走普通类批次。',
        'dual_line_rule': '须同时满足省文化课控制线与省专业统考合格线，否则无法投档对应本科志愿。',
        'pro_max_scores': {'艺术类': ART_PRO_MAX, '体育类': SPORTS_PRO_MAX},
        'art_formulas': [{'id': k, 'label': v} for k, v in ART_FORMULA_LABELS.items()],
        'sports_formulas': [{'id': k, 'label': v} for k, v in SPORTS_FORMULA_LABELS.items()],
        'default_formula': {'艺术类本科': 5, '艺术类专科': 5, '体育类本科': 3, '体育类专科': 3},
        'rank_notice': '河南省不发布艺体综合分官方一分一段位次；请用院校近3年同公式最低综合分对标冲稳保，勿套用普通类文化课位次。',
        'volunteer_slots': VOLUNTEER_SLOTS,
        'rhyme': RHYME,
        'art_batches': ART_TARGET_BATCHES,
        'sports_batches': SPORTS_TARGET_BATCHES,
    }


def calculate_composite(data: dict[str, Any]) -> dict[str, Any]:
    category = data.get('category') or ''
    if category not in ('艺术类', '体育类'):
        raise ValueError('类别须为艺术类或体育类')
    culture = float(data.get('culture_score') or data.get('score') or 0)
    pro = float(data.get('professional_score') or 0)
    batch_level = data.get('batch_level') or '本科'
    formula_id = int(data.get('formula_id') or default_formula_id(category, batch_level))
    waive = bool(data.get('waive_art_sports_batch'))
    culture_cutoff = data.get('culture_cutoff')
    pro_cutoff = data.get('pro_cutoff')
    culture_cutoff_f = float(culture_cutoff) if culture_cutoff not in (None, '') else None
    pro_cutoff_f = float(pro_cutoff) if pro_cutoff not in (None, '') else None

    if waive:
        return {
            'category': category,
            'waive_art_sports_batch': True,
            'composite_score': culture,
            'formula_id': 1,
            'formula_label': '已放弃艺体批次，按普通类文化课分',
            'dual_line': {'dual_line_ok': True, 'message': '已切换普通类志愿算法'},
            'use_normal_track': True,
        }

    dual = check_dual_line(culture, pro, culture_cutoff_f, pro_cutoff_f, category)
    if category == '艺术类':
        composite = calc_art_composite(culture, pro, formula_id)
        label = ART_FORMULA_LABELS.get(formula_id, '')
    else:
        composite = calc_sports_composite(culture, pro, formula_id)
        label = SPORTS_FORMULA_LABELS.get(formula_id, '')

    return {
        'category': category,
        'culture_score': culture,
        'professional_score': pro,
        'formula_id': formula_id,
        'formula_label': label,
        'composite_score': composite,
        'dual_line': dual,
        'use_normal_track': False,
        'can_recommend_undergraduate': dual['dual_line_ok'] and batch_level == '本科',
        'can_recommend_junior': dual['dual_line_ok'] or batch_level == '专科',
    }


def _avg_min_composite(school: dict[str, Any]) -> float:
    values = [school.get('min_composite_2025'), school.get('min_composite_2024'), school.get('min_composite_2023')]
    nums = [float(v) for v in values if v is not None]
    return sum(nums) / len(nums) if nums else 0.0


def match_schools(data: dict[str, Any]) -> dict[str, Any]:
    calc = calculate_composite(data)
    if calc.get('use_normal_track'):
        raise ValueError('已放弃艺体批次，请使用普通类志愿检索')

    category = data.get('category')
    batch_level = data.get('batch_level') or '本科'
    composite = float(calc['composite_score'])
    formula_id = int(calc['formula_id'])

    if batch_level == '本科' and not calc['dual_line'].get('dual_line_ok'):
        return {
            **calc,
            'eligible': False,
            'message': '未满足双过线，本科院校推荐已屏蔽；可填专科或勾选放弃艺体批次走普通类。',
            'groups': {'rush': [], 'steady': [], 'safe': []},
        }

    schools = [
        s for s in SAMPLE_SCHOOLS
        if s['category'] == category and s['batch_level'] == batch_level and int(s['formula_id']) == formula_id
    ]
    ranked: list[dict[str, Any]] = []
    for school in schools:
        ref = _avg_min_composite(school)
        diff = composite - ref
        if diff >= 8:
            tier = 'rush'
            tier_label = '冲刺'
        elif diff >= -5:
            tier = 'steady'
            tier_label = '稳妥'
        else:
            tier = 'safe'
            tier_label = '保底'
        ranked.append({
            **school,
            'ref_min_composite': round(ref, 2),
            'score_diff': round(diff, 2),
            'tier': tier,
            'tier_label': tier_label,
        })

    ranked.sort(key=lambda item: (-item['ref_min_composite'], -item['score_diff']))
    groups = {
        'rush': [x for x in ranked if x['tier'] == 'rush'],
        'steady': [x for x in ranked if x['tier'] == 'steady'],
        'safe': [x for x in ranked if x['tier'] == 'safe'],
    }
    return {
        **calc,
        'eligible': True,
        'message': '按院校对应公式与近3年最低综合分对标，划分冲稳保（非官方位次）。',
        'groups': groups,
        'total': len(ranked),
        'volunteer_slots': VOLUNTEER_SLOTS,
    }
