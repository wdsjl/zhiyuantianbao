"""
全国高考数据采集配置

覆盖掌上高考 static-data API 支持的全部 31 个生源省份（不含港澳台）。
后台可按省份、预设方案一键触发采集。
"""

from __future__ import annotations

from typing import Any, TypedDict


class ProvinceConfig(TypedDict):
    name: str
    source_id: str
    region: str
    sort_order: int


class CrawlPreset(TypedDict):
    key: str
    label: str
    school_limit: int | None
    recent_years: int
    description: str


# 掌上高考生源省份 ID，与 province/list.json 一致
PROVINCE_CONFIGS: list[ProvinceConfig] = [
    {'name': '北京', 'source_id': '11', 'region': '华北', 'sort_order': 1},
    {'name': '天津', 'source_id': '12', 'region': '华北', 'sort_order': 2},
    {'name': '河北', 'source_id': '13', 'region': '华北', 'sort_order': 3},
    {'name': '山西', 'source_id': '14', 'region': '华北', 'sort_order': 4},
    {'name': '内蒙古', 'source_id': '15', 'region': '华北', 'sort_order': 5},
    {'name': '辽宁', 'source_id': '21', 'region': '东北', 'sort_order': 6},
    {'name': '吉林', 'source_id': '22', 'region': '东北', 'sort_order': 7},
    {'name': '黑龙江', 'source_id': '23', 'region': '东北', 'sort_order': 8},
    {'name': '上海', 'source_id': '31', 'region': '华东', 'sort_order': 9},
    {'name': '江苏', 'source_id': '32', 'region': '华东', 'sort_order': 10},
    {'name': '浙江', 'source_id': '33', 'region': '华东', 'sort_order': 11},
    {'name': '安徽', 'source_id': '34', 'region': '华东', 'sort_order': 12},
    {'name': '福建', 'source_id': '35', 'region': '华东', 'sort_order': 13},
    {'name': '江西', 'source_id': '36', 'region': '华东', 'sort_order': 14},
    {'name': '山东', 'source_id': '37', 'region': '华东', 'sort_order': 15},
    {'name': '河南', 'source_id': '41', 'region': '华中', 'sort_order': 16},
    {'name': '湖北', 'source_id': '42', 'region': '华中', 'sort_order': 17},
    {'name': '湖南', 'source_id': '43', 'region': '华中', 'sort_order': 18},
    {'name': '广东', 'source_id': '44', 'region': '华南', 'sort_order': 19},
    {'name': '广西', 'source_id': '45', 'region': '华南', 'sort_order': 20},
    {'name': '海南', 'source_id': '46', 'region': '华南', 'sort_order': 21},
    {'name': '重庆', 'source_id': '50', 'region': '西南', 'sort_order': 22},
    {'name': '四川', 'source_id': '51', 'region': '西南', 'sort_order': 23},
    {'name': '贵州', 'source_id': '52', 'region': '西南', 'sort_order': 24},
    {'name': '云南', 'source_id': '53', 'region': '西南', 'sort_order': 25},
    {'name': '西藏', 'source_id': '54', 'region': '西南', 'sort_order': 26},
    {'name': '陕西', 'source_id': '61', 'region': '西北', 'sort_order': 27},
    {'name': '甘肃', 'source_id': '62', 'region': '西北', 'sort_order': 28},
    {'name': '青海', 'source_id': '63', 'region': '西北', 'sort_order': 29},
    {'name': '宁夏', 'source_id': '64', 'region': '西北', 'sort_order': 30},
    {'name': '新疆', 'source_id': '65', 'region': '西北', 'sort_order': 31},
]

PROVINCE_IDS: dict[str, str] = {item['name']: item['source_id'] for item in PROVINCE_CONFIGS}
PROVINCE_BY_ID: dict[str, str] = {item['source_id']: item['name'] for item in PROVINCE_CONFIGS}
REGION_ORDER = ['华北', '东北', '华东', '华中', '华南', '西南', '西北']

CRAWL_PRESETS: dict[str, CrawlPreset] = {
    'trial': {
        'key': 'trial',
        'label': '试跑',
        'school_limit': 20,
        'recent_years': 3,
        'description': '20 所院校 × 近三年，用于验证配置与网络',
    },
    'full_recent_3y': {
        'key': 'full_recent_3y',
        'label': '近三年全量',
        'school_limit': None,
        'recent_years': 3,
        'description': '全部院校 × 近三年录取位次、分数线与招生计划',
    },
    'full_recent_1y': {
        'key': 'full_recent_1y',
        'label': '最近一年全量',
        'school_limit': None,
        'recent_years': 1,
        'description': '全部院校 × 最近一年数据',
    },
}


def list_provinces(region: str | None = None) -> list[ProvinceConfig]:
    items = PROVINCE_CONFIGS
    if region:
        items = [item for item in items if item['region'] == region]
    return sorted(items, key=lambda item: item['sort_order'])


def get_province_config(name: str) -> ProvinceConfig | None:
    for item in PROVINCE_CONFIGS:
        if item['name'] == name:
            return item
    return None


def get_preset(key: str) -> CrawlPreset:
    preset = CRAWL_PRESETS.get(key)
    if not preset:
        raise ValueError(f'未知采集预设：{key}')
    return preset


def resolve_preset_options(preset_key: str, years: list[int] | None = None) -> dict[str, Any]:
    from crawler_service import default_recent_years

    preset = get_preset(preset_key)
    selected_years = years or default_recent_years(preset['recent_years'])
    return {
        'preset': preset,
        'school_limit': preset['school_limit'],
        'years': selected_years,
    }


def cli_command(province: str, preset_key: str = 'full_recent_3y') -> str:
    preset = get_preset(preset_key)
    limit = 0 if preset['school_limit'] is None else preset['school_limit']
    return (
        f'python crawler_service.py --province {province} '
        f'--recent-years {preset["recent_years"]} --limit {limit}'
    )
