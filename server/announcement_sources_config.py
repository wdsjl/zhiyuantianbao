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
    '招生', '章程', '简章', '计划', '公告', '录取', '报考', '选科',
)

# 强相关：标题或 URL 至少命中其一，否则视为非招生公告
STRONG_RECRUIT_TITLE_KEYWORDS: tuple[str, ...] = (
    '招生', '章程', '简章', '计划', '录取', '报考', '选科', '投档', '本科招生', '专科招生',
)
STRONG_RECRUIT_URL_HINTS: tuple[str, ...] = (
    'zsb', 'zhaosheng', 'recruit', 'bkzs', 'zsjy', '/zs/', 'zsxx', 'zsjz', 'lqfs', 'zxgg',
)

# 命中则直接排除（招标采购、校庆新闻、人事招聘等）
EXCLUDE_KEYWORDS: tuple[str, ...] = (
    '招标', '投标', '采购', '竞争性磋商', '竞争性谈判', '中标', '成交公告', '询价',
    '食堂', '无人机', '工作站', '设备', '仪器', '维修', '改造', '升级项目',
    '校友', '论坛', '荣誉', '表彰', '教师节', '人才支持计划', '人才培养支持', '人才计划',
    '交通管制', '管制通告', '周年', '校庆', '人事', '招聘启事', '公开招聘', '科研', '基金',
    '会议通知', '图书馆', '体检', '疫苗', '预决算', '审计', '党建', '党课', '主题教育',
    '获奖', '竞赛获奖', '表彰大会', '座谈会', '学术报告', '讲座', '放假', '开学',
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
