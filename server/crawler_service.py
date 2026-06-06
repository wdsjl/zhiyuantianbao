"""
高考数据采集服务

数据来源：掌上高考 static-data.gaokao.cn（教育部阳光高考平台合作数据服务）
采集内容：全国院校库、分省专业录取分数线、招生计划，并写入本地 SQLite。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from db import get_connection, row_to_dict
from import_service import import_admission_rows, get_or_create_school, get_or_create_major, upsert_plan, upsert_admission, insert_import_log

BASE_URL = 'https://static-data.gaokao.cn/www/2.0'
USER_AGENT = 'Mozilla/5.0 ZhiyuanGaokaoCrawler/1.0 (+local research)'
REQUEST_INTERVAL = 0.2

# 掌上高考「生源省份」ID（用于 schoolspecialscore / schoolspecialplan）
PROVINCE_IDS: dict[str, str] = {
    '北京': '11', '天津': '12', '河北': '13', '山西': '14', '内蒙古': '15',
    '辽宁': '21', '吉林': '22', '黑龙江': '23', '上海': '31', '江苏': '32',
    '浙江': '33', '安徽': '34', '福建': '35', '江西': '36', '山东': '37',
    '河南': '41', '湖北': '42', '湖南': '43', '广东': '44', '广西': '45',
    '海南': '46', '重庆': '50', '四川': '51', '贵州': '52', '云南': '53',
    '西藏': '54', '陕西': '61', '甘肃': '62', '青海': '63', '宁夏': '64', '新疆': '65',
}


def ensure_crawl_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS crawl_logs (
              crawl_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_name TEXT NOT NULL,
              province TEXT NOT NULL,
              year INTEGER NOT NULL,
              school_total INTEGER NOT NULL DEFAULT 0,
              school_processed INTEGER NOT NULL DEFAULT 0,
              row_total INTEGER NOT NULL DEFAULT 0,
              row_success INTEGER NOT NULL DEFAULT 0,
              row_fail INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'running',
              error_message TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            )
            '''
        )
        connection.commit()


def fetch_json(path: str) -> dict[str, Any] | list[Any] | None:
    url = path if path.startswith('http') else f'{BASE_URL}/{path.lstrip("/")}'
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Referer': 'https://www.gaokao.cn/'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def fetch_school_list() -> dict[str, dict[str, Any]]:
    payload = fetch_json('school/list_v2.json')
    if not payload or payload.get('code') != '0000':
        raise RuntimeError('无法获取全国院校列表')
    return payload.get('data') or {}


def fetch_school_detail(school_id: str) -> dict[str, Any] | None:
    payload = fetch_json(f'school/{school_id}/info.json')
    if not payload or payload.get('code') != '0000':
        return None
    return payload.get('data')


def fetch_batch_items(path: str) -> list[dict[str, Any]]:
    payload = fetch_json(path)
    if not payload or payload.get('code') != '0000':
        return []
    data = payload.get('data') or {}
    items: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, dict):
                items.extend(value.get('item') or [])
    return items


def bool_flag(value: Any) -> int:
    text = str(value or '').strip()
    return 1 if text in ('1', 'true', 'True') else 0


def parse_optional_int(value: Any) -> int | None:
    if value is None or value == '' or value == '-':
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def default_recent_years(count: int = 3, end_year: int | None = None) -> list[int]:
    """返回最近若干录取年份（默认不含当年，因数据可能未公布）。"""
    from datetime import datetime
    current = datetime.now().year
    latest = end_year if end_year is not None else current - 1
    return [latest - offset for offset in range(count)]


def normalize_batch_name(name: str) -> str:
    mapping = {
        '平行录取一段': '普通类一段',
        '普通类平行录取': '普通类一段',
        '普通类平行录取一段': '普通类一段',
    }
    return mapping.get(name, name or '普通类一段')


def major_code_from_item(item: dict[str, Any]) -> str:
    code = str(item.get('spcode') or '').strip()
    if code:
        return code
    spe_id = item.get('spe_id') or item.get('special_id')
    return f'G{spe_id}' if spe_id else f'M{item.get("spname", "unknown")[:12]}'


def plan_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        key = f'{item.get("spe_id")}:{item.get("special_id")}:{item.get("spname")}'
        result[key] = item
    return result


def find_plan_for_score(score_item: dict[str, Any], plans: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    keys = [
        f'{score_item.get("spe_id")}:{score_item.get("special_id")}:{score_item.get("spname")}',
        f'{score_item.get("spe_id")}:{score_item.get("special_id")}:{score_item.get("sp_name")}',
    ]
    for key in keys:
        if key in plans:
            return plans[key]
    for plan in plans.values():
        if plan.get('spe_id') == score_item.get('spe_id') and plan.get('sp_name') == score_item.get('sp_name'):
            return plan
    return None


def build_import_row(
    school_brief: dict[str, Any],
    school_detail: dict[str, Any] | None,
    score_item: dict[str, Any],
    plan_item: dict[str, Any] | None,
    year: int,
    province_name: str,
) -> dict[str, Any]:
    detail = school_detail or {}
    school_name = detail.get('name') or school_brief.get('name') or ''
    school_code = str(detail.get('zs_code') or detail.get('code_enroll') or school_brief.get('school_id') or '').strip()
    if len(school_code) > 5:
        school_code = school_code[:5]
    plan = plan_item or {}
    major_name = score_item.get('spname') or score_item.get('sp_name') or plan.get('spname') or '未知专业'
    major_code = major_code_from_item(plan if plan else score_item)
    return {
        'year': year,
        'province': province_name,
        'batch': normalize_batch_name(score_item.get('local_batch_name') or plan.get('local_batch_name') or ''),
        'school_code': school_code,
        'school_name': school_name,
        'school_province': school_brief.get('p') or detail.get('belong') or '',
        'city': school_brief.get('c') or '',
        'school_type': (detail.get('attr_list') or [''])[-1] if isinstance(detail.get('attr_list'), list) else '',
        'education_level': school_brief.get('level') or '本科',
        'is_985': bool_flag(detail.get('f985') if detail else school_brief.get('f985')),
        'is_211': bool_flag(detail.get('f211') if detail else school_brief.get('f211')),
        'is_double_first_class': bool_flag(detail.get('dual_class') if detail else school_brief.get('dual_class')),
        'is_public': 0 if (school_brief.get('nature') == '民办' or detail.get('school_nature') == '36001') else 1,
        'major_code': major_code,
        'major_name': major_name,
        'major_category': score_item.get('level2_name') or plan.get('level2_name') or '',
        'major_type': score_item.get('level3_name') or plan.get('level3_name') or '',
        'degree_type': '本科',
        'duration': plan.get('length') or '',
        'subject_requirement': score_item.get('sp_info') or plan.get('sp_info') or '',
        'enrollment_count': int(plan.get('num') or 0) or None,
        'tuition': int(float(plan.get('tuition') or 0)) if plan.get('tuition') else None,
        'min_score': parse_optional_int(score_item.get('min')),
        'min_rank': parse_optional_int(score_item.get('min_section')),
        'avg_score': parse_optional_int(score_item.get('average')),
        'max_score': parse_optional_int(score_item.get('max')),
        'max_rank': parse_optional_int(score_item.get('max_section')),
    }


def crawl_school_rows(school_id: str, school_brief: dict[str, Any], year: int, province_name: str, province_id: str) -> list[dict[str, Any]]:
    detail = fetch_school_detail(school_id)
    time.sleep(REQUEST_INTERVAL)
    score_items = fetch_batch_items(f'schoolspecialscore/{school_id}/{year}/{province_id}.json')
    time.sleep(REQUEST_INTERVAL)
    plan_items = fetch_batch_items(f'schoolspecialplan/{school_id}/{year}/{province_id}.json')
    plans = plan_map(plan_items)
    rows = []
    for score_item in score_items:
        if parse_optional_int(score_item.get('min')) is None and parse_optional_int(score_item.get('min_section')) is None:
            continue
        plan_item = find_plan_for_score(score_item, plans)
        rows.append(build_import_row(school_brief, detail, score_item, plan_item, year, province_name))
    return rows


def start_crawl_log(province: str, year: int, school_total: int) -> int:
    ensure_crawl_tables()
    with get_connection() as connection:
        cursor = connection.execute(
            'INSERT INTO crawl_logs (source_name, province, year, school_total, status) VALUES (?, ?, ?, ?, ?)',
            ['掌上高考 static-data.gaokao.cn', province, year, school_total, 'running']
        )
        connection.commit()
        return cursor.lastrowid


def finish_crawl_log(crawl_id: int, processed: int, row_total: int, success: int, fail: int, status: str, error_message: str | None = None) -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE crawl_logs SET school_processed = ?, row_total = ?, row_success = ?, row_fail = ?,
              status = ?, error_message = ?, finished_at = CURRENT_TIMESTAMP
            WHERE crawl_id = ?
            ''',
            [processed, row_total, success, fail, status, error_message, crawl_id]
        )
        connection.commit()


def list_crawl_logs(limit: int = 20) -> list[dict[str, Any]]:
    ensure_crawl_tables()
    with get_connection() as connection:
        from db import rows_to_dicts
        return rows_to_dicts(connection.execute(
            'SELECT * FROM crawl_logs ORDER BY crawl_id DESC LIMIT ?', [limit]
        ).fetchall())


def build_school_row(school_brief: dict[str, Any], school_detail: dict[str, Any] | None, school_id: str) -> dict[str, Any]:
    detail = school_detail or {}
    school_name = detail.get('name') or school_brief.get('name') or ''
    school_code = str(detail.get('zs_code') or detail.get('code_enroll') or school_brief.get('school_id') or school_id).strip()
    if len(school_code) > 5:
        school_code = school_code[:5]
    return {
        'school_code': school_code,
        'school_name': school_name,
        'school_province': school_brief.get('p') or detail.get('belong') or '',
        'city': school_brief.get('c') or '',
        'school_type': (detail.get('attr_list') or [''])[-1] if isinstance(detail.get('attr_list'), list) else '',
        'education_level': school_brief.get('level') or '本科',
        'is_985': bool_flag(detail.get('f985') if detail else school_brief.get('f985')),
        'is_211': bool_flag(detail.get('f211') if detail else school_brief.get('f211')),
        'is_double_first_class': bool_flag(detail.get('dual_class') if detail else school_brief.get('dual_class')),
        'is_public': 0 if (school_brief.get('nature') == '民办' or detail.get('school_nature') == '36001') else 1,
    }


def get_crawl_log(crawl_id: int) -> dict[str, Any] | None:
    ensure_crawl_tables()
    with get_connection() as connection:
        row = connection.execute('SELECT * FROM crawl_logs WHERE crawl_id = ?', [crawl_id]).fetchone()
        return row_to_dict(row) if row else None


def import_schools_only(limit: int | None = None) -> dict[str, Any]:
    schools = fetch_school_list()
    school_ids = list(schools.keys())
    if limit:
        school_ids = school_ids[:limit]
    success = 0
    errors: list[str] = []
    with get_connection() as connection:
        for school_id in school_ids:
            brief = schools[school_id]
            try:
                detail = fetch_school_detail(school_id)
                time.sleep(REQUEST_INTERVAL)
                row = build_school_row(brief, detail, school_id)
                get_or_create_school(connection, row)
                success += 1
            except Exception as exc:
                errors.append(f'{school_id}: {exc}')
        connection.commit()
    return {'total': len(school_ids), 'success': success, 'errors': errors[:20]}


def crawl_and_import_years(
    province: str,
    years: list[int],
    school_limit: int | None = 50,
    on_progress: Callable[[int, int, str, int], None] | None = None,
) -> dict[str, Any]:
    if not years:
        raise ValueError('请至少指定一个录取年份')
    years = sorted(set(years), reverse=True)
    combined: dict[str, Any] = {
        'province': province,
        'years': years,
        'year_results': [],
        'total_count': 0,
        'success_count': 0,
        'fail_count': 0,
        'school_processed': 0,
        'crawl_ids': [],
        'crawl_errors': [],
        'errors': [],
    }
    for year in years:
        def year_progress(done: int, total: int, name: str, current_year: int = year) -> None:
            if on_progress:
                on_progress(done, total, name, current_year)

        result = crawl_and_import(province, year, school_limit, year_progress)
        combined['year_results'].append(result)
        combined['total_count'] += result.get('total_count', 0)
        combined['success_count'] += result.get('success_count', 0)
        combined['fail_count'] += result.get('fail_count', 0)
        combined['school_processed'] = max(combined['school_processed'], result.get('school_processed', 0))
        if result.get('crawl_id'):
            combined['crawl_ids'].append(result['crawl_id'])
        combined['crawl_errors'].extend(result.get('crawl_errors') or [])
        combined['errors'].extend(result.get('errors') or [])
    combined['crawl_errors'] = combined['crawl_errors'][:20]
    combined['errors'] = combined['errors'][:20]
    return combined


def crawl_and_import(
    province: str,
    year: int,
    school_limit: int | None = 50,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    province_id = PROVINCE_IDS.get(province)
    if not province_id:
        raise ValueError(f'不支持的省份：{province}')

    schools = fetch_school_list()
    school_ids = list(schools.keys())
    if school_limit:
        school_ids = school_ids[:school_limit]

    crawl_id = start_crawl_log(province, year, len(school_ids))
    all_rows: list[dict[str, Any]] = []
    processed = 0

    try:
        for school_id in school_ids:
            brief = schools[school_id]
            school_name = brief.get('name', school_id)
            if on_progress:
                try:
                    on_progress(processed, len(school_ids), school_name, year)
                except TypeError:
                    on_progress(processed, len(school_ids), school_name)
            try:
                rows = crawl_school_rows(school_id, brief, year, province, province_id)
                all_rows.extend(rows)
            except Exception as exc:
                all_rows.append({
                    '__error__': f'{school_name}({school_id}): {exc}'
                })
            processed += 1

        valid_rows = [row for row in all_rows if '__error__' not in row]
        errors = [row['__error__'] for row in all_rows if '__error__' in row]
        result = import_admission_rows(f'crawler_{province}_{year}.json', valid_rows)
        result['crawl_id'] = crawl_id
        result['school_processed'] = processed
        result['crawl_errors'] = errors[:20]
        finish_crawl_log(
            crawl_id, processed, result['total_count'], result['success_count'], result['fail_count'],
            'success' if not errors else 'partial', '\n'.join(errors[:20]) or result.get('errors', [''])[0] if result.get('errors') else None
        )
        return result
    except Exception as exc:
        finish_crawl_log(crawl_id, processed, len(all_rows), 0, len(all_rows), 'failed', str(exc))
        raise


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='采集掌上高考数据并导入数据库')
    parser.add_argument('--province', default='浙江', help='生源省份，例如 浙江')
    parser.add_argument('--year', type=int, help='单个录取年份')
    parser.add_argument('--years', help='多个年份，逗号分隔，如 2024,2023,2022')
    parser.add_argument('--recent-years', type=int, default=0, help='采集最近 N 年（默认从昨年起算）')
    parser.add_argument('--limit', type=int, default=20, help='最多采集院校数量，0 表示全部')
    parser.add_argument('--schools-only', action='store_true', help='仅同步院校库，不采集分数线')
    args = parser.parse_args()
    limit = None if args.limit == 0 else args.limit
    if args.schools_only:
        print(import_schools_only(limit))
    else:
        if args.years:
            years = [int(item.strip()) for item in args.years.split(',') if item.strip()]
        elif args.recent_years:
            years = default_recent_years(args.recent_years)
        elif args.year:
            years = [args.year]
        else:
            years = [2024]

        def progress(done, total, name, year=None):
            prefix = f'[{year}] ' if year else ''
            print(f'{prefix}[{done + 1}/{total}] {name}')

        if len(years) == 1:
            print(crawl_and_import(args.province, years[0], limit, progress))
        else:
            print(crawl_and_import_years(args.province, years, limit, progress))
