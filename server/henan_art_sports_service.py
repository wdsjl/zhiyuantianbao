"""河南艺术类 / 体育类志愿填报规则与综合分计算（小程序直接复用）。"""
from __future__ import annotations

import sqlite3
from typing import Any, Callable

from db import get_connection

PROVINCE = '河南'
ART_PRO_MAX = 300
SPORTS_PRO_MAX = 150
VOLUNTEER_SLOTS = 64
VOLUNTEER_MODE = '专业+院校'
VOLUNTEER_RULE_DESCRIPTION = (
    '艺术本科批使用统考成绩的专业采用64个「专业+院校」平行志愿填报模式，投档规则与往年一致'
    '（分数优先、遵循志愿、一次投档，同分先比专业分）。'
)

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
        'rank_notice': '河南省不发布艺体综合分官方一分一段位次；优先使用已导入录取库（艺考批次最低分）对标冲稳保，勿套用普通类文化课位次。',
        'volunteer_slots': VOLUNTEER_SLOTS,
        'volunteer_mode': VOLUNTEER_MODE,
        'volunteer_rule_description': VOLUNTEER_RULE_DESCRIPTION,
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
    if school.get('ref_min_composite') is not None:
        return float(school['ref_min_composite'])
    values = [school.get('min_composite_2025'), school.get('min_composite_2024'), school.get('min_composite_2023')]
    nums = [float(v) for v in values if v is not None]
    return sum(nums) / len(nums) if nums else 0.0


def _message_for_data_source(source: str) -> str:
    if source == 'admission_records':
        return '按已导入录取库历年最低分（综合分）对标冲稳保，非官方位次。'
    if source == 'art_sports_admissions':
        return '按艺体专项库历年最低综合分对标冲稳保（非官方位次）。'
    return '按示例院校历年最低综合分对标冲稳保（非官方位次）；建议导入录取数据后自动切换。'


def load_from_admission_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    """优先使用普通录取导入库中的艺考/体育批次数据（最低分视为综合分参考）。"""
    from recommend_service import query_admission_rows

    province = data.get('province') or PROVINCE
    batch = data.get('batch') or ''
    subject = data.get('subject_combination') or ''
    exam_type = data.get('exam_type') or data.get('category') or '艺术类'
    category = category_from_exam_type(exam_type) if exam_type in ('艺术类', '体育类') else str(exam_type)
    batch_level = batch_level_from_target_batch(batch)
    formula_id = data.get('art_sports_formula_id') or data.get('formula_id')
    if formula_id in (None, ''):
        formula_id = default_formula_id(category, batch_level)
    else:
        formula_id = int(formula_id)

    rows = query_admission_rows(province, batch, subject)
    if not rows and subject:
        rows = query_admission_rows(province, batch, '')
    if not rows:
        return []

    year_weights = [0.5, 0.3, 0.2]
    grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get('min_score') is None:
            continue
        key = (row['school_id'], row['major_id'])
        grouped.setdefault(key, []).append(row)

    schools: list[dict[str, Any]] = []
    for records in grouped.values():
        sorted_records = sorted(records, key=lambda item: int(item.get('year') or 0), reverse=True)[:3]
        weight_sum = 0.0
        score_sum = 0.0
        latest = sorted_records[0]
        year_scores: dict[int, float] = {}
        for index, record in enumerate(sorted_records):
            weight = year_weights[index] if index < len(year_weights) else 0.0
            if record.get('min_score') is not None:
                score = float(record['min_score'])
                score_sum += score * weight
                weight_sum += weight
                year_scores[int(record.get('year') or 0)] = score
        if not weight_sum:
            continue
        ref = round(score_sum / weight_sum, 2)
        schools.append({
            'school_id': latest.get('school_id'),
            'major_id': latest.get('major_id'),
            'school_name': latest.get('school_name'),
            'major_name': latest.get('major_name'),
            'school_code': latest.get('school_code') or '',
            'major_code': latest.get('major_code') or '',
            'category': category,
            'batch_level': batch_level,
            'formula_id': formula_id,
            'ref_min_composite': ref,
            'min_composite_2025': year_scores.get(2025),
            'min_composite_2024': year_scores.get(2024),
            'min_composite_2023': year_scores.get(2023),
            'city': latest.get('city') or '',
            'school_type': latest.get('school_type'),
            'tuition': latest.get('tuition'),
            'duration': latest.get('duration'),
            'major_type': latest.get('major_type'),
            'data_source': 'admission_records',
        })
    return schools


def load_art_sports_candidates(data: dict[str, Any], category: str, batch_level: str, formula_id: int) -> tuple[list[dict[str, Any]], str]:
    merged = {
        **data,
        'exam_type': category,
        'batch': data.get('batch') or '',
        'subject_combination': data.get('subject_combination') or '',
    }
    try:
        from_import = load_from_admission_records(merged)
    except sqlite3.OperationalError:
        from_import = []
    if from_import:
        return from_import, 'admission_records'

    ensure_art_sports_admissions_table()
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT * FROM art_sports_admissions
            WHERE province = ? AND category = ? AND batch_level = ? AND formula_id = ?
            ORDER BY min_composite_2025 DESC
            ''',
            [PROVINCE, category, batch_level, int(formula_id)],
        ).fetchall()
    if rows:
        return [{**dict(row), 'data_source': 'art_sports_admissions'} for row in rows], 'art_sports_admissions'

    sample = [
        {**s, 'data_source': 'sample'}
        for s in EXTENDED_SAMPLE_SCHOOLS
        if s['category'] == category and s['batch_level'] == batch_level and int(s['formula_id']) == int(formula_id)
    ]
    return sample, 'sample'


def match_schools(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(data)
    if merged.get('category') and 'exam_type' not in merged:
        merged['exam_type'] = merged['category']
    if not merged.get('batch') and merged.get('batch_level'):
        cat = merged.get('category') or merged.get('exam_type') or '艺术类'
        prefix = '艺术' if cat == '艺术类' else '体育'
        merged['batch'] = f'{prefix}{merged["batch_level"]}批'
    ctx = _build_match_context(merged)
    ranked = ctx.get('ranked') or []
    groups = {
        'rush': [x for x in ranked if x.get('tier') == 'rush'],
        'steady': [x for x in ranked if x.get('tier') == 'steady'],
        'safe': [x for x in ranked if x.get('tier') == 'safe'],
    }
    return {
        **{k: v for k, v in ctx.items() if k not in ('ranked', 'batch_level', 'data_source')},
        'groups': groups,
        'total': len(ranked),
        'volunteer_slots': VOLUNTEER_SLOTS,
    }


TIER_TO_GRADIENT = {'rush': '冲', 'steady': '稳', 'safe': '保'}
GRADIENT_TO_TIER = {'冲': 'rush', '稳': 'steady', '保': 'safe'}


def _normalize_province(province: str) -> str:
    return str(province or '').replace('省', '').replace(' ', '')


def _infer_exam_type(data: dict[str, Any]) -> str:
    exam_type = str(data.get('exam_type') or '普通类')
    batch = str(data.get('batch') or '')
    if exam_type in ('艺术类', '体育类'):
        return exam_type
    if '艺术' in batch:
        return '艺术类'
    if '体育' in batch:
        return '体育类'
    return exam_type


def is_art_sports_request(data: dict[str, Any]) -> bool:
    if bool(data.get('waive_art_sports_batch')):
        return False
    if _normalize_province(data.get('province') or '') != PROVINCE:
        return False
    exam_type = _infer_exam_type(data)
    return exam_type in ('艺术类', '体育类')


def batch_level_from_target_batch(batch: str) -> str:
    return '专科' if '专科' in str(batch or '') else '本科'


def category_from_exam_type(exam_type: str) -> str:
    if exam_type == '体育类':
        return '体育类'
    if exam_type == '艺术类':
        return '艺术类'
    raise ValueError('考试类别须为艺术类或体育类')


def request_to_match_payload(data: dict[str, Any]) -> dict[str, Any]:
    exam_type = _infer_exam_type(data)
    batch_level = batch_level_from_target_batch(data.get('batch') or '')
    formula_id = data.get('art_sports_formula_id') or data.get('formula_id')
    if formula_id in (None, ''):
        formula_id = default_formula_id(category_from_exam_type(exam_type), batch_level)
    return {
        'category': category_from_exam_type(exam_type),
        'culture_score': float(data.get('score') or data.get('culture_score') or 0),
        'professional_score': float(data.get('professional_score') or 0),
        'formula_id': int(formula_id),
        'batch_level': batch_level,
        'culture_cutoff': data.get('culture_cutoff'),
        'pro_cutoff': data.get('pro_cutoff'),
        'waive_art_sports_batch': bool(data.get('waive_art_sports_batch')),
    }


def ensure_art_sports_admissions_table() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS art_sports_admissions (
              admission_id INTEGER PRIMARY KEY AUTOINCREMENT,
              province TEXT NOT NULL DEFAULT '河南',
              category TEXT NOT NULL,
              batch_level TEXT NOT NULL,
              school_name TEXT NOT NULL,
              major_name TEXT NOT NULL,
              formula_id INTEGER NOT NULL,
              min_composite_2025 REAL,
              min_composite_2024 REAL,
              min_composite_2023 REAL,
              city TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE (province, category, batch_level, school_name, major_name, formula_id)
            )
            '''
        )
        count = connection.execute('SELECT COUNT(*) AS count FROM art_sports_admissions').fetchone()['count']
        if not count:
            for school in EXTENDED_SAMPLE_SCHOOLS:
                connection.execute(
                    '''
                    INSERT INTO art_sports_admissions (
                      province, category, batch_level, school_name, major_name, formula_id,
                      min_composite_2025, min_composite_2024, min_composite_2023, city
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    [
                        PROVINCE,
                        school['category'],
                        school['batch_level'],
                        school['school_name'],
                        school['major_name'],
                        int(school['formula_id']),
                        school.get('min_composite_2025'),
                        school.get('min_composite_2024'),
                        school.get('min_composite_2023'),
                        school.get('city') or '',
                    ],
                )
        connection.commit()


def load_art_sports_admissions(category: str, batch_level: str, formula_id: int) -> list[dict[str, Any]]:
    """兼容旧调用：优先录取导入库，再艺体专项库，最后示例数据。"""
    schools, _source = load_art_sports_candidates(
        {'province': PROVINCE, 'batch': f'{"艺术" if category == "艺术类" else "体育"}{batch_level}批'},
        category,
        batch_level,
        int(formula_id),
    )
    return schools


def _pseudo_id(prefix: str, name: str) -> int:
    return abs(hash(f'{prefix}:{name}')) % 900000 + 100000


def resolve_school_major_ids(school_name: str, major_name: str, category: str = '') -> tuple[int, int]:
    """为艺体志愿草稿解析或创建院校/专业 ID，避免外键约束失败。"""
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS schools (
              school_id INTEGER PRIMARY KEY AUTOINCREMENT,
              school_code TEXT NOT NULL UNIQUE,
              school_name TEXT NOT NULL,
              province TEXT,
              city TEXT,
              school_type TEXT,
              education_level TEXT,
              is_985 INTEGER NOT NULL DEFAULT 0,
              is_211 INTEGER NOT NULL DEFAULT 0,
              is_double_first_class INTEGER NOT NULL DEFAULT 0,
              is_public INTEGER NOT NULL DEFAULT 1,
              authority TEXT,
              website TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS majors (
              major_id INTEGER PRIMARY KEY AUTOINCREMENT,
              major_code TEXT NOT NULL UNIQUE,
              major_name TEXT NOT NULL,
              major_category TEXT,
              major_type TEXT,
              degree_type TEXT,
              duration TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        school = connection.execute(
            'SELECT school_id FROM schools WHERE school_name = ? LIMIT 1', [school_name]
        ).fetchone()
        if school:
            school_id = school['school_id']
        else:
            code = f'AS{abs(hash(school_name)) % 100000:05d}'
            school_id = connection.execute(
                'INSERT INTO schools (school_code, school_name, province) VALUES (?, ?, ?)',
                [code, school_name, PROVINCE],
            ).lastrowid
        major = connection.execute(
            'SELECT major_id FROM majors WHERE major_name = ? LIMIT 1', [major_name]
        ).fetchone()
        if major:
            major_id = major['major_id']
        else:
            code = f'AM{abs(hash(major_name)) % 100000:05d}'
            major_id = connection.execute(
                'INSERT INTO majors (major_code, major_name, major_type) VALUES (?, ?, ?)',
                [code, major_name, category or '艺体'],
            ).lastrowid
        connection.commit()
    return int(school_id), int(major_id)


EXTENDED_SAMPLE_SCHOOLS: list[dict[str, Any]] = SAMPLE_SCHOOLS + [
    {'school_name': '河南工业大学', 'major_name': '环境设计', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 5, 'min_composite_2025': 468.0, 'min_composite_2024': 464.0, 'min_composite_2023': 460.0, 'city': '郑州'},
    {'school_name': '中原工学院', 'major_name': '服装与服饰设计', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 5, 'min_composite_2025': 455.0, 'min_composite_2024': 450.0, 'min_composite_2023': 446.0, 'city': '郑州'},
    {'school_name': '河南科技大学', 'major_name': '产品设计', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 5, 'min_composite_2025': 462.0, 'min_composite_2024': 458.0, 'min_composite_2023': 454.0, 'city': '洛阳'},
    {'school_name': '南阳师范学院', 'major_name': '播音与主持艺术', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 5, 'min_composite_2025': 445.0, 'min_composite_2024': 440.0, 'min_composite_2023': 436.0, 'city': '南阳'},
    {'school_name': '安阳师范学院', 'major_name': '书法学', 'category': '艺术类', 'batch_level': '本科', 'formula_id': 4, 'min_composite_2025': 438.0, 'min_composite_2024': 434.0, 'min_composite_2023': 430.0, 'city': '安阳'},
    {'school_name': '周口师范学院', 'major_name': '美术学', 'category': '艺术类', 'batch_level': '专科', 'formula_id': 5, 'min_composite_2025': 405.0, 'min_composite_2024': 400.0, 'min_composite_2023': 395.0, 'city': '周口'},
    {'school_name': '河南检察职业学院', 'major_name': '数字媒体艺术设计', 'category': '艺术类', 'batch_level': '专科', 'formula_id': 5, 'min_composite_2025': 390.0, 'min_composite_2024': 385.0, 'min_composite_2023': 380.0, 'city': '郑州'},
    {'school_name': '河南农业大学', 'major_name': '体育教育', 'category': '体育类', 'batch_level': '本科', 'formula_id': 3, 'min_composite_2025': 615.0, 'min_composite_2024': 610.0, 'min_composite_2023': 605.0, 'city': '郑州'},
    {'school_name': '河南师范大学', 'major_name': '体育教育', 'category': '体育类', 'batch_level': '本科', 'formula_id': 3, 'min_composite_2025': 600.0, 'min_composite_2024': 595.0, 'min_composite_2023': 590.0, 'city': '新乡'},
    {'school_name': '洛阳师范学院', 'major_name': '运动康复', 'category': '体育类', 'batch_level': '本科', 'formula_id': 3, 'min_composite_2025': 585.0, 'min_composite_2024': 580.0, 'min_composite_2023': 575.0, 'city': '洛阳'},
    {'school_name': '平顶山学院', 'major_name': '社会体育', 'category': '体育类', 'batch_level': '专科', 'formula_id': 3, 'min_composite_2025': 565.0, 'min_composite_2024': 560.0, 'min_composite_2023': 555.0, 'city': '平顶山'},
]


def _classify_tier(score_diff: float) -> tuple[str, str]:
    if score_diff >= 8:
        return 'rush', '冲刺'
    if score_diff >= -5:
        return 'steady', '稳妥'
    return 'safe', '保底'


def _rank_school_rows(calc: dict[str, Any], schools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    composite = float(calc['composite_score'])
    ranked: list[dict[str, Any]] = []
    for school in schools:
        ref = _avg_min_composite(school)
        diff = composite - ref
        tier, tier_label = _classify_tier(diff)
        ranked.append({
            **school,
            'ref_min_composite': round(ref, 2),
            'score_diff': round(diff, 2),
            'tier': tier,
            'tier_label': tier_label,
            'gradient_type': TIER_TO_GRADIENT[tier],
        })
    ranked.sort(key=lambda item: (-item['ref_min_composite'], -item['score_diff']))
    return ranked


def _build_match_context(data: dict[str, Any]) -> dict[str, Any]:
    payload = request_to_match_payload(data)
    calc = calculate_composite({**payload, 'category': payload['category']})
    if calc.get('use_normal_track'):
        raise ValueError('已放弃艺体批次，请使用普通类志愿检索')
    category = payload['category']
    batch_level = payload['batch_level']
    formula_id = int(calc['formula_id'])
    if batch_level == '本科' and not calc['dual_line'].get('dual_line_ok'):
        return {
            **calc,
            'eligible': False,
            'message': '未满足双过线，本科院校推荐已屏蔽；可填专科或勾选放弃艺体批次走普通类。',
            'ranked': [],
        }
    schools, data_source = load_art_sports_candidates(data, category, batch_level, formula_id)
    ranked = _rank_school_rows(calc, schools)
    return {
        **calc,
        'eligible': True,
        'message': _message_for_data_source(data_source),
        'ranked': ranked,
        'batch_level': batch_level,
        'data_source': data_source,
        'candidate_count': len(schools),
    }


def _art_sports_risk_reason(gradient: str, is_adjustable: bool, ref_composite: Any) -> str:
    ref_text = f'参考最低综合分 {ref_composite}' if ref_composite not in (None, '') else ''
    if gradient == '冲' and not is_adjustable:
        return f'当前志愿为冲刺档，且未选择服从调剂，存在较高退档风险。{ref_text}'.strip()
    if gradient == '冲':
        base = '院校参考最低综合分偏高，建议保留稳妥志愿兜底。'
        return f'{base} {ref_text}'.strip() if ref_text else base
    if not is_adjustable:
        return '未选择服从调剂，达到院校投档线后仍可能因专业未录取而退档。'
    if gradient == '保':
        return f'当前志愿结构相对稳妥，仍需以考试院和高校官方信息为准。{ref_text}'.strip()
    return f'当前志愿结构相对稳妥，仍需以考试院和高校官方信息为准。{ref_text}'.strip()


def _pool_item_from_ranked(row: dict[str, Any], *, accept_adjustment: bool) -> dict[str, Any]:
    school_name = row.get('school_name') or ''
    major_name = row.get('major_name') or ''
    category = row.get('category') or ''
    if row.get('school_id') and row.get('major_id'):
        school_id, major_id = int(row['school_id']), int(row['major_id'])
    else:
        school_id, major_id = resolve_school_major_ids(school_name, major_name, category)
    gradient = row.get('gradient_type') or TIER_TO_GRADIENT.get(row.get('tier') or '', '稳')
    return {
        'gradient_type': gradient,
        'school_id': school_id,
        'school_name': school_name,
        'school_code': row.get('school_code') or '',
        'major_id': major_id,
        'major_name': major_name,
        'major_code': row.get('major_code') or '',
        'major_type': row.get('major_type') or row.get('category') or '',
        'city': row.get('city') or '',
        'school_type': row.get('school_type') or '',
        'tuition': row.get('tuition'),
        'duration': row.get('duration'),
        'min_score': row.get('ref_min_composite'),
        'min_rank': None,
        'weighted_score': row.get('ref_min_composite'),
        'weighted_rank': None,
        'years_used': [2025, 2024, 2023],
        'admission_probability': f'综合分分差 {row.get("score_diff")}',
        'preference_score': 0,
        'personality_matched': False,
        'is_adjustable': accept_adjustment,
        'risk_level': '低' if gradient == '保' else ('中' if gradient == '稳' else '高'),
        'risk_reason': _art_sports_risk_reason(
            gradient,
            accept_adjustment,
            row.get('ref_min_composite'),
        ),
        'ref_min_composite': row.get('ref_min_composite'),
        'score_diff': row.get('score_diff'),
        'formula_id': row.get('formula_id'),
        'art_sports_mode': True,
        'data_source': row.get('data_source') or 'unknown',
    }


def query_art_sports_eligible_pool(
    data: dict[str, Any],
    *,
    gradient: str = '',
    keyword: str = '',
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    context = _build_match_context(data)
    ranked = context.get('ranked') or []
    pool = [_pool_item_from_ranked(row, accept_adjustment=bool(data.get('accept_adjustment', True))) for row in ranked]
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
    total = len(pool)
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    start = (page - 1) * page_size
    items = pool[start:start + page_size]
    summary = {'冲': 0, '稳': 0, '保': 0, '垫': 0, 'total': len(ranked)}
    for row in ranked:
        gradient_type = row.get('gradient_type') or '稳'
        if gradient_type in summary:
            summary[gradient_type] += 1
    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'summary': summary,
        'strategy': {
            'mode': 'art_sports_composite',
            'composite_score': context.get('composite_score'),
            'formula_label': context.get('formula_label'),
            'dual_line': context.get('dual_line'),
            'eligible': context.get('eligible'),
            'message': context.get('message'),
            'volunteer_slots': VOLUNTEER_SLOTS,
            'rank_notice': '河南省不发布艺体综合分官方位次，以下为历年最低综合分对标结果。',
            'data_source': context.get('data_source'),
            'candidate_count': context.get('candidate_count'),
        },
        'user_rank': None,
        'composite_score': context.get('composite_score'),
        'art_sports_mode': True,
    }


PARALLEL_LAYOUT_NOTE = '平行志愿按志愿序号有序排布：前段冲、中段稳、后段保（分数优先、遵循志愿）。'


def get_art_sports_quotas(plan_style: str) -> dict[str, int]:
    quotas = {'冲': 16, '稳': 24, '保': 24}
    if plan_style == 'aggressive':
        quotas = {'冲': 24, '稳': 24, '保': 16}
    elif plan_style == 'conservative':
        quotas = {'冲': 12, '稳': 20, '保': 32}
    return quotas


def assemble_art_sports_parallel_plan(
    all_items: list[dict[str, Any]],
    plan_style: str,
    *,
    total_slots: int = VOLUNTEER_SLOTS,
) -> list[dict[str, Any]]:
    """64个「专业+院校」平行志愿：高位冲、中位稳、低位保，同档按参考综合分从高到低。"""
    order = {'冲': 0, '稳': 1, '保': 2}
    ranked = sorted(
        all_items,
        key=lambda row: (
            order.get(row.get('gradient_type') or '稳', 9),
            -(row.get('ref_min_composite') or 0),
            row.get('school_name') or '',
            row.get('major_name') or '',
        ),
    )
    quotas = get_art_sports_quotas(plan_style)
    buckets: dict[str, list[dict[str, Any]]] = {'冲': [], '稳': [], '保': []}
    for item in ranked:
        gradient = item.get('gradient_type') or '稳'
        if gradient not in buckets:
            continue
        if len(buckets[gradient]) >= quotas.get(gradient, 0):
            continue
        buckets[gradient].append(item)

    selected: list[dict[str, Any]] = []
    for gradient in ('冲', '稳', '保'):
        selected.extend(buckets[gradient])

    if len(selected) < total_slots:
        used = {(item['school_name'], item['major_name']) for item in selected}
        for item in ranked:
            key = (item['school_name'], item['major_name'])
            if key in used:
                continue
            selected.append(item)
            used.add(key)
            if len(selected) >= total_slots:
                break

    selected = selected[:total_slots]
    for index, item in enumerate(selected, start=1):
        item['sort_order'] = index
    return selected


def build_art_sports_recommendation(data: dict[str, Any]) -> dict[str, Any]:
    pool_result = query_art_sports_eligible_pool(data, page=1, page_size=500)
    if not pool_result.get('strategy', {}).get('eligible'):
        return {
            'items': [],
            'risk': {'level': '高', 'count': {}, 'warnings': [pool_result.get('strategy', {}).get('message') or '暂无推荐']},
            'strategy': pool_result.get('strategy'),
            'generation': {'target_slots': VOLUNTEER_SLOTS, 'generated_count': 0, 'candidate_pool': 0},
            'art_sports_mode': True,
        }
    all_items = query_art_sports_eligible_pool(data, page=1, page_size=500)['items']
    quotas = get_art_sports_quotas(data.get('plan_style') or 'balanced')
    selected = assemble_art_sports_parallel_plan(all_items, data.get('plan_style') or 'balanced')
    warnings = []
    if len(selected) < VOLUNTEER_SLOTS and pool_result.get('strategy', {}).get('data_source') == 'admission_records':
        warnings.append(f'已使用导入录取库 {pool_result.get("strategy", {}).get("candidate_count", 0)} 条候选，当前生成 {len(selected)}/{VOLUNTEER_SLOTS} 个志愿。')
    elif len(selected) < VOLUNTEER_SLOTS:
        warnings.append(f'候选数据 {len(all_items)} 条，当前生成 {len(selected)}/{VOLUNTEER_SLOTS} 个志愿，可补充艺体录取数据。')
    return {
        'items': selected,
        'risk': {
            'level': '低' if selected else '高',
            'count': {'冲': sum(1 for x in selected if x.get('gradient_type') == '冲'), '稳': sum(1 for x in selected if x.get('gradient_type') == '稳'), '保': sum(1 for x in selected if x.get('gradient_type') == '保')},
            'warnings': warnings,
        },
        'strategy': {
            **(pool_result.get('strategy') or {}),
            'volunteer_rule': {
                'total_slots': VOLUNTEER_SLOTS,
                'school_count': VOLUNTEER_SLOTS,
                'batch': data.get('batch'),
                'volunteer_mode': VOLUNTEER_MODE,
                'matched': True,
                'source': 'henan_art_sports',
                'rule_description': VOLUNTEER_RULE_DESCRIPTION,
            },
            'quotas': quotas,
            'parallel_layout': PARALLEL_LAYOUT_NOTE,
        },
        'generation': {
            'target_slots': VOLUNTEER_SLOTS,
            'generated_count': len(selected),
            'candidate_pool': len(all_items),
        },
        'art_sports_mode': True,
    }
