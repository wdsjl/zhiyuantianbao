"""各省高考志愿填报数量规则（2025），供推荐引擎按省足额生成志愿。"""

from __future__ import annotations

from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts

RULE_YEAR = 2025

# volunteer_mode: 院校专业组 | 专业平行志愿 | 专业+院校
# school_count: 平行志愿志愿单位数量（院校专业组模式下为组数，专业平行志愿模式下为专业+院校数）
PROVINCE_RULES_2025: list[dict[str, Any]] = [
    # —— 专业(类)+院校 / 专业平行志愿 ——
    {'province': '浙江', 'batch': '普通类一段', 'volunteer_mode': '专业平行志愿', 'school_count': 80, 'major_count_per_school': 1, 'rule_description': '1个专业(类)+1所院校为1个志愿，一段最多80个。'},
    {'province': '浙江', 'batch': '普通类二段', 'volunteer_mode': '专业平行志愿', 'school_count': 80, 'major_count_per_school': 1, 'rule_description': '二段最多80个专业平行志愿。'},
    {'province': '浙江', 'batch': '普通类三段', 'volunteer_mode': '专业平行志愿', 'school_count': 80, 'major_count_per_school': 1, 'rule_description': '三段最多80个专业平行志愿。'},
    {'province': '山东', 'batch': '普通类一段', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '1个专业(类)+1所院校为1个志愿，一段最多96个。'},
    {'province': '山东', 'batch': '普通类二段', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '二段最多96个。'},
    {'province': '山东', 'batch': '专科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '专科批最多96个。'},
    {'province': '河北', 'batch': '本科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '本科批96个专业平行志愿。'},
    {'province': '河北', 'batch': '专科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '专科批96个。'},
    {'province': '辽宁', 'batch': '本科批', 'volunteer_mode': '专业+院校', 'school_count': 112, 'major_count_per_school': 1, 'rule_description': '本科批112个专业+院校志愿，全国最多。'},
    {'province': '辽宁', 'batch': '专科批', 'volunteer_mode': '专业+院校', 'school_count': 60, 'major_count_per_school': 1, 'rule_description': '专科批60个。'},
    {'province': '重庆', 'batch': '本科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '本科批96个。'},
    {'province': '重庆', 'batch': '专科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '专科批96个。'},
    {'province': '贵州', 'batch': '本科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '本科批96个。'},
    {'province': '贵州', 'batch': '专科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '专科批96个。'},
    {'province': '青海', 'batch': '本科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '本科批96个。'},
    {'province': '青海', 'batch': '专科批', 'volunteer_mode': '专业+院校', 'school_count': 96, 'major_count_per_school': 1, 'rule_description': '专科批96个。'},
    # —— 院校专业组 ——
    {'province': '河南', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 48, 'major_count_per_school': 6, 'rule_description': '2025新高考：48个院校专业组，每组最多6个专业+调剂选项。'},
    {'province': '河南', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 48, 'major_count_per_school': 6, 'rule_description': '专科批48个院校专业组。'},
    {'province': '北京', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 30, 'major_count_per_school': 6, 'rule_description': '本科普通批30个院校专业组。'},
    {'province': '北京', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 20, 'major_count_per_school': 6, 'rule_description': '专科批20个。'},
    {'province': '天津', 'batch': '本科批A段', 'volunteer_mode': '院校专业组', 'school_count': 50, 'major_count_per_school': 6, 'rule_description': '本科A段50个院校专业组。'},
    {'province': '天津', 'batch': '本科批B段', 'volunteer_mode': '院校专业组', 'school_count': 25, 'major_count_per_school': 6, 'rule_description': '本科B段25个。'},
    {'province': '天津', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 20, 'major_count_per_school': 6, 'rule_description': '专科批20个。'},
    {'province': '上海', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 24, 'major_count_per_school': 4, 'rule_description': '本科批24个院校专业组，每组最多4个专业。'},
    {'province': '上海', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 8, 'major_count_per_school': 6, 'rule_description': '专科批8个。'},
    {'province': '海南', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 30, 'major_count_per_school': 6, 'rule_description': '本科批30个。'},
    {'province': '海南', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 10, 'major_count_per_school': 6, 'rule_description': '专科批10个。'},
    {'province': '广东', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个院校专业组。'},
    {'province': '广东', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '湖南', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '湖南', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 30, 'major_count_per_school': 6, 'rule_description': '专科批30个。'},
    {'province': '湖北', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '湖北', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 20, 'major_count_per_school': 6, 'rule_description': '专科批20个。'},
    {'province': '江苏', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '本科批40个。'},
    {'province': '江苏', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '专科批40个。'},
    {'province': '福建', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '福建', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '专科批40个。'},
    {'province': '安徽', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '安徽', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '江西', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '江西', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '广西', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '广西', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '专科批40个。'},
    {'province': '甘肃', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '甘肃', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '吉林', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '本科批40个。'},
    {'province': '吉林', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '专科批40个。'},
    {'province': '黑龙江', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '本科批40个。'},
    {'province': '黑龙江', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '专科批40个。'},
    {'province': '四川', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '四川', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '陕西', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '陕西', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '山西', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '山西', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '内蒙古', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '内蒙古', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '宁夏', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '本科批45个。'},
    {'province': '宁夏', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 45, 'major_count_per_school': 6, 'rule_description': '专科批45个。'},
    {'province': '云南', 'batch': '本科批', 'volunteer_mode': '院校专业组', 'school_count': 40, 'major_count_per_school': 6, 'rule_description': '本科批40个。'},
    {'province': '云南', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 20, 'major_count_per_school': 6, 'rule_description': '专科批20个。'},
    {'province': '新疆', 'batch': '本科一批', 'volunteer_mode': '院校专业组', 'school_count': 9, 'major_count_per_school': 6, 'rule_description': '本科一批9个平行志愿。'},
    {'province': '新疆', 'batch': '本科二批', 'volunteer_mode': '院校专业组', 'school_count': 18, 'major_count_per_school': 6, 'rule_description': '本科二批18个。'},
    {'province': '新疆', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 9, 'major_count_per_school': 6, 'rule_description': '专科批9个。'},
    {'province': '西藏', 'batch': '本科一批', 'volunteer_mode': '院校专业组', 'school_count': 4, 'major_count_per_school': 6, 'rule_description': '本科一批4个。'},
    {'province': '西藏', 'batch': '本科二批', 'volunteer_mode': '院校专业组', 'school_count': 8, 'major_count_per_school': 6, 'rule_description': '本科二批8个。'},
    {'province': '西藏', 'batch': '专科批', 'volunteer_mode': '院校专业组', 'school_count': 9, 'major_count_per_school': 6, 'rule_description': '专科批9个。'},
]

DEFAULT_VOLUNTEER_COUNT = 45
LEGACY_DEFAULT_VOLUNTEER_COUNT = 9


def normalize_volunteer_override(count: int | None) -> int | None:
    """0 或历史客户端默认 9 均表示按省份规则生成，不使用固定条数。"""
    value = int(count or 0)
    if value <= 0 or value == LEGACY_DEFAULT_VOLUNTEER_COUNT:
        return None
    return value


DEFAULT_RULE = {
    'province': '',
    'year': RULE_YEAR,
    'batch': '本科批',
    'volunteer_mode': '院校专业组',
    'school_count': DEFAULT_VOLUNTEER_COUNT,
    'major_count_per_school': 6,
    'is_parallel_volunteer': 1,
    'adjustment_supported': 1,
    'score_priority_rule': '分数优先，遵循志愿',
    'rule_description': '未匹配到本省规则时使用的默认值，请在后台核对各省最新政策。',
}


def _normalize_province(province: str) -> str:
    value = (province or '').strip()
    for suffix in ('省', '市', '自治区', '壮族自治区', '回族自治区', '维吾尔自治区'):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value


def _batch_category(batch: str) -> str:
    text = (batch or '').strip()
    if not text:
        return 'undergraduate'
    if any(key in text for key in ('专科', '高职', '高专')):
        return 'junior'
    if '二段' in text and '一段' not in text:
        return 'segment2'
    if '三段' in text:
        return 'segment3'
    if any(key in text for key in ('二批', '本科二批', 'B段')):
        return 'batch2'
    if any(key in text for key in ('一批', '本科一批', 'A段', '一段')):
        return 'batch1'
    return 'undergraduate'


def _rule_category(batch: str) -> str:
    text = (batch or '').strip()
    if any(key in text for key in ('专科', '高职', '高专')):
        return 'junior'
    if '三段' in text:
        return 'segment3'
    if '二段' in text or '二批' in text or 'B段' in text:
        return 'segment2'
    if '一段' in text or '一批' in text or 'A段' in text:
        return 'batch1'
    return 'undergraduate'


def _score_rule_match(user_batch: str, rule_batch: str) -> int:
    user_batch = (user_batch or '').strip()
    rule_batch = (rule_batch or '').strip()
    if user_batch == rule_batch:
        return 100
    if user_batch and user_batch in rule_batch:
        return 80
    if rule_batch and rule_batch in user_batch:
        return 75
    user_cat = _batch_category(user_batch)
    rule_cat = _rule_category(rule_batch)
    if user_cat == rule_cat:
        return 60
    # 学生档案写「本科批」，山东/浙江等实际批次名可能是「普通类一段」
    if user_cat == 'undergraduate' and rule_cat in ('undergraduate', 'batch1'):
        return 62
    if user_cat == 'junior' and rule_cat == 'junior':
        return 60
    return 0


def ensure_province_rules_seeded() -> None:
    with get_connection() as connection:
        for item in PROVINCE_RULES_2025:
            connection.execute(
                '''
                INSERT INTO province_rules (
                  province, year, batch, volunteer_mode, school_count, major_count_per_school,
                  is_parallel_volunteer, adjustment_supported, score_priority_rule, rule_description
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, '分数优先，遵循志愿', ?)
                ON CONFLICT(province, year, batch) DO UPDATE SET
                  volunteer_mode = excluded.volunteer_mode,
                  school_count = excluded.school_count,
                  major_count_per_school = excluded.major_count_per_school,
                  adjustment_supported = excluded.adjustment_supported,
                  rule_description = excluded.rule_description,
                  updated_at = CURRENT_TIMESTAMP
                ''',
                [
                    item['province'],
                    RULE_YEAR,
                    item['batch'],
                    item['volunteer_mode'],
                    int(item['school_count']),
                    int(item.get('major_count_per_school') or 1),
                    0 if item.get('volunteer_mode') in ('专业平行志愿', '专业+院校') else 1,
                    item.get('rule_description') or '',
                ],
            )
        connection.commit()


def list_rules_for_province(province: str, year: int = RULE_YEAR) -> list[dict[str, Any]]:
    normalized = _normalize_province(province)
    with get_connection() as connection:
        rows = rows_to_dicts(
            connection.execute(
                '''
                SELECT * FROM province_rules
                WHERE year = ? AND (province = ? OR province = ?)
                ORDER BY batch ASC
                ''',
                [year, province.strip(), normalized],
            ).fetchall()
        )
    return rows


def find_province_rule(
    province: str,
    batch: str,
    year: int = RULE_YEAR,
) -> dict[str, Any]:
    province = (province or '').strip()
    batch = (batch or '').strip()
    normalized = _normalize_province(province)
    if not province:
        return {**DEFAULT_RULE, 'matched': False, 'match_score': 0}

    with get_connection() as connection:
        rows = rows_to_dicts(
            connection.execute(
                '''
                SELECT * FROM province_rules
                WHERE year = ? AND (province = ? OR province = ?)
                ''',
                [year, province, normalized],
            ).fetchall()
        )

    if not rows:
        return {
            **DEFAULT_RULE,
            'province': normalized or province,
            'batch': batch or DEFAULT_RULE['batch'],
            'matched': False,
            'match_score': 0,
        }

    if batch:
        scored = sorted(
            ((row, _score_rule_match(batch, row.get('batch') or '')) for row in rows),
            key=lambda item: item[1],
            reverse=True,
        )
        best_row, best_score = scored[0]
        if best_score >= 60:
            return {**best_row, 'matched': True, 'match_score': best_score, 'requested_batch': batch}

    # 无批次时优先返回本科批 / 普通类一段
    preferred = None
    for candidate in rows:
        name = candidate.get('batch') or ''
        if name in ('本科批', '普通类一段'):
            preferred = candidate
            break
    chosen = preferred or rows[0]
    return {
        **chosen,
        'matched': True,
        'match_score': 50,
        'requested_batch': batch or chosen.get('batch'),
    }


def resolve_volunteer_slots(
    province: str,
    batch: str,
    year: int = RULE_YEAR,
    override_count: int | None = None,
) -> dict[str, Any]:
    override_count = normalize_volunteer_override(override_count)
    if override_count is not None and int(override_count) > 0:
        rule = find_province_rule(province, batch, year)
        return {
            'total_slots': int(override_count),
            'rule': rule,
            'source': 'override',
        }

    rule = find_province_rule(province, batch, year)
    total_slots = int(rule.get('school_count') or DEFAULT_VOLUNTEER_COUNT)
    return {
        'total_slots': max(1, total_slots),
        'rule': rule,
        'source': 'province_rule' if rule.get('matched') else 'default',
    }


def summarize_province_rules() -> list[dict[str, Any]]:
    """按省份汇总志愿模式与主要批次志愿数，供文档/后台展示。"""
    grouped: dict[str, dict[str, Any]] = {}
    for item in PROVINCE_RULES_2025:
        province = item['province']
        entry = grouped.setdefault(
            province,
            {
                'province': province,
                'volunteer_mode': item['volunteer_mode'],
                'batches': [],
            },
        )
        if item['volunteer_mode'] != entry['volunteer_mode']:
            entry['volunteer_mode'] = '混合模式'
        entry['batches'].append(
            {
                'batch': item['batch'],
                'school_count': item['school_count'],
                'major_count_per_school': item.get('major_count_per_school') or 1,
            }
        )
    return sorted(grouped.values(), key=lambda row: row['province'])
