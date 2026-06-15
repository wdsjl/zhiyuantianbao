"""全国 / 河南 2026 招生公告采集源配置。"""

from __future__ import annotations

from typing import Any

ANNOUNCEMENT_YEAR_DEFAULT = 2026

# 省级考试院 / 官方平台列表页（link_discovery + 列表解析）
PROVINCIAL_ANNOUNCEMENT_SOURCES: list[dict[str, Any]] = [
    {
        'source_org': '河南省教育考试院',
        'source_type': 'provincial',
        'province': '河南',
        'priority': 1,
        'urls': [
            'https://www.haeea.cn/',
            'https://www.haeea.cn/a/gkbm/',
            'https://www.haeea.cn/a/gkbm/zxgg/',
        ],
        'remark': '河南招生公告优先源',
    },
    {
        'source_org': '阳光高考信息平台',
        'source_type': 'national_platform',
        'province': '',
        'priority': 2,
        'urls': [
            'https://gaokao.chsi.com.cn/zxdy/',
            'https://gaokao.chsi.com.cn/zxdy/zxdy-zsjz-lqfs.shtml',
        ],
        'remark': '教育部阳光高考招生动态',
    },
]

# 高校官网常见招生栏目路径（相对官网根路径拼接）
SCHOOL_RECRUIT_PATHS: tuple[str, ...] = (
    '/zsjy.htm',
    '/zsb/',
    '/zsb/index.htm',
    '/zs/',
    '/recruit/',
    '/bkzs/',
    '/bkzsxxw/',
    '/zhaosheng/',
    '/news/zsxx/',
    '/index/zsxx.htm',
)

# 公告标题 / URL 关键词（需同时命中招生类 + 年份或可推断为最新招生）
RECRUIT_KEYWORDS: tuple[str, ...] = (
    '招生', '章程', '简章', '计划', '公告', '录取', '报考', '专业', '选科',
)
YEAR_KEYWORDS: tuple[str, ...] = ('2026', '26年', '二〇二六')

ANNOUNCEMENT_TYPES: tuple[str, ...] = (
    '招生公告',
    '招生章程',
    '招生计划',
    '招生简章',
    '录取信息',
    '招生官网',
    '其他招生信息',
)
