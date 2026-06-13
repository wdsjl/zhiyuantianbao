"""
河南高考录取数据采集服务

采集河南省近 3 年（默认）全量院校专业录取数据，写入 admission_records 与 enrollment_plans。
数据来源：掌上高考 static-data.gaokao.cn（阳光高考合作数据）。

采集字段：
- 录取分数：最低分、平均分、最高分
- 录取位次：最低位次、最高位次
- 录取人数：实际录取人数（lq_num）或招生计划人数
- 志愿填报相关：批次、选科要求、学费、学制、校区、招生类型、专业组、备注
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from crawler_config import get_preset
from crawler_service import (
    crawl_and_import_years,
    default_recent_years,
    get_province_data_overview,
    has_running_crawl,
    log_progress,
    run_crawl_job,
)
from db import get_connection, rows_to_dicts

HENAN_PROVINCE = '河南'
HENAN_SOURCE_ID = '41'
HENAN_PRESET_KEY = 'henan_full_3y'
DEFAULT_YEARS = 3


def henan_recent_years(count: int = DEFAULT_YEARS) -> list[int]:
    return default_recent_years(count)


def run_henan_admission_crawl(
    years: list[int] | None = None,
    school_limit: int | None = None,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """采集河南指定年份全量录取与招生计划数据。"""
    selected_years = years or henan_recent_years()
    if has_running_crawl(HENAN_PROVINCE):
        raise RuntimeError(f'{HENAN_PROVINCE} 已有采集任务在运行，请稍后再试')
    log_progress(
        f'河南录取数据采集开始：年份 {", ".join(str(year) for year in selected_years)}，'
        f'院校范围 {"全量" if school_limit is None else f"{school_limit} 所"}'
    )
    if len(selected_years) == 1:
        from crawler_service import crawl_and_import
        return crawl_and_import(HENAN_PROVINCE, selected_years[0], school_limit, on_progress)
    return crawl_and_import_years(HENAN_PROVINCE, selected_years, school_limit, on_progress)


def run_henan_preset_job(on_progress: Callable[..., None] | None = None) -> dict[str, Any]:
    return run_crawl_job(HENAN_PROVINCE, HENAN_PRESET_KEY, on_progress=on_progress)


def get_henan_admission_summary() -> dict[str, Any]:
    """查询河南本地录取数据统计，供后台展示。"""
    summary: dict[str, Any] = {
        'province': HENAN_PROVINCE,
        'source_id': HENAN_SOURCE_ID,
        'years': henan_recent_years(),
        'is_running': has_running_crawl(HENAN_PROVINCE),
        'year_stats': [],
        'totals': {
            'admission_count': 0,
            'plan_count': 0,
            'school_count': 0,
            'rank_count': 0,
            'score_count': 0,
        },
    }
    with get_connection() as connection:
        year_stats = rows_to_dicts(connection.execute(
            '''
            SELECT year,
                   COUNT(*) AS admission_count,
                   COUNT(DISTINCT school_id) AS school_count,
                   SUM(CASE WHEN min_rank IS NOT NULL THEN 1 ELSE 0 END) AS rank_count,
                   SUM(CASE WHEN min_score IS NOT NULL THEN 1 ELSE 0 END) AS score_count,
                   SUM(CASE WHEN enrollment_count IS NOT NULL THEN 1 ELSE 0 END) AS admitted_count
            FROM admission_records
            WHERE province IN ('河南', '河南省')
            GROUP BY year
            ORDER BY year DESC
            '''
        ).fetchall())
        plan_stats = rows_to_dicts(connection.execute(
            '''
            SELECT year, COUNT(*) AS plan_count
            FROM enrollment_plans
            WHERE province IN ('河南', '河南省')
            GROUP BY year
            ORDER BY year DESC
            '''
        ).fetchall())
        plan_by_year = {row['year']: row['plan_count'] for row in plan_stats}
        for row in year_stats:
            row['plan_count'] = plan_by_year.get(row['year'], 0)
            summary['year_stats'].append(row)
            summary['totals']['admission_count'] += row.get('admission_count', 0) or 0
            summary['totals']['plan_count'] += row.get('plan_count', 0) or 0
            summary['totals']['school_count'] = max(summary['totals']['school_count'], row.get('school_count', 0) or 0)
            summary['totals']['rank_count'] += row.get('rank_count', 0) or 0
            summary['totals']['score_count'] += row.get('score_count', 0) or 0

    for item in get_province_data_overview():
        if item['name'] == HENAN_PROVINCE:
            summary['last_crawl_at'] = item.get('last_crawl_at')
            summary['last_success_at'] = item.get('last_success_at')
            break
    return summary


def cli_command_trial() -> str:
    return 'python henan_admission_crawler_service.py --trial'


def cli_command_full() -> str:
    return 'python henan_admission_crawler_service.py --full'


def _progress(done: int, total: int, name: str, year: int | None = None) -> None:
    prefix = f'[{year}] ' if year else ''
    if done == 0 or (done + 1) % 10 == 0 or done + 1 == total:
        log_progress(f'河南 {prefix}[{done + 1}/{total}] {name}')


def _run_cli(args: argparse.Namespace) -> None:
    if args.summary:
        print(get_henan_admission_summary(), flush=True)
        return

    if args.trial:
        result = run_henan_admission_crawl(years=henan_recent_years(), school_limit=20, on_progress=_progress)
    elif args.full or args.preset:
        preset_key = args.preset or HENAN_PRESET_KEY
        get_preset(preset_key)
        result = run_henan_preset_job(on_progress=_progress)
    else:
        years = henan_recent_years(args.years or DEFAULT_YEARS)
        if args.year_list:
            years = [int(item.strip()) for item in args.year_list.split(',') if item.strip()]
        limit = None if args.limit == 0 else args.limit
        result = run_henan_admission_crawl(years=years, school_limit=limit, on_progress=_progress)

    log_progress('河南录取数据采集完成。')
    print(result, flush=True)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    parser = argparse.ArgumentParser(description='采集河南省高考录取全量数据')
    parser.add_argument('--trial', action='store_true', help='试跑：20 所院校 × 近三年')
    parser.add_argument('--full', action='store_true', help='全量：全部院校 × 近三年（与后台一键采集相同）')
    parser.add_argument('--preset', choices=['henan_full_3y', 'full_recent_3y', 'trial'], help='使用预设方案')
    parser.add_argument('--years', type=int, default=0, help='采集最近 N 年（默认 3）')
    parser.add_argument('--year-list', dest='year_list', help='指定年份，逗号分隔，如 2025,2024,2023')
    parser.add_argument('--limit', type=int, default=0, help='院校数量上限，0 表示全量')
    parser.add_argument('--summary', action='store_true', help='仅查看河南本地数据统计')
    cli_args = parser.parse_args()
    _run_cli(cli_args)
