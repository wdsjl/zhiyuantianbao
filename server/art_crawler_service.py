"""
艺术类 / 体育类录取数据采集服务

数据来源：掌上高考 static-data.gaokao.cn API
采集内容：河南（可扩展）艺术本科批 / 艺术专科批 / 体育本科批 / 体育专科批
          的综合分录取线，写入 art_sports_admissions 表。

与普通类 crawler_service.py 的关键区别：
- 目标批次为艺术类/体育类（type=25/28 或 batch_name 含 艺术/体育）
- min_score 即为综合分（非文化课分），无官方位次
- 需推断 formula_id（河南艺术本科默认公式⑤=0.5W+1.25Z）
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from db import get_connection, row_to_dict, rows_to_dicts
from llm_settings_service import chat_completion, get_llm_settings

BASE_URL = 'https://static-data.gaokao.cn/www/2.0'
USER_AGENT = 'Mozilla/5.0 ZhiyuanGaokaoCrawler/1.0 (+art sports)'
REQUEST_INTERVAL = 0.25

# 河南艺体默认公式
ART_DEFAULT_FORMULA_ID = 5       # 文化50% + 专业50%
SPORTS_DEFAULT_FORMULA_ID = 3    # 文化50% + 专业50%

# 艺术类 / 体育类在 API 中的 type 值（经验值，可能变化）
ART_TYPE_CODES = {'25', '26', '27'}      # 25=艺术统考, 26/27 可能为其他艺术子类
SPORTS_TYPE_CODES = {'28', '29'}          # 体育类

# 批次匹配关键词（用于区分艺术/体育/普通）
ART_BATCH_KEYWORDS = ['艺术']
SPORTS_BATCH_KEYWORDS = ['体育']

# 每个省份每批次每公式最小记录数
MIN_RECORDS_PER_BATCH = 30


def log_progress(message: str) -> None:
    print(message, flush=True)


# ── API 数据获取 ────────────────────────────────────────────

def fetch_json(path: str) -> dict[str, Any] | list[Any] | None:
    url = path if path.startswith('http') else f'{BASE_URL}/{path.lstrip("/")}'
    request = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Referer': 'https://www.gaokao.cn/',
    })
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def fetch_school_list() -> dict[str, dict[str, Any]]:
    payload = fetch_json('school/list_v2.json')
    if not payload or payload.get('code') != '0000':
        raise RuntimeError('无法获取全国院校列表')
    return payload.get('data') or {}


def fetch_school_scores(school_id: str, year: int, province_id: str) -> list[dict[str, Any]]:
    """获取某校某年某省的所有录取数据，返回扁平化的 item 列表。"""
    items: list[dict[str, Any]] = []
    payload = fetch_json(f'schoolspecialscore/{school_id}/{year}/{province_id}.json')
    if not payload or payload.get('code') != '0000':
        return items
    data = payload.get('data') or {}
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, dict):
                items.extend(value.get('item') or [])
    return items


# ── 批次/类别判断 ──────────────────────────────────────────

def is_art_batch(batch_name: str) -> bool:
    return any(kw in str(batch_name) for kw in ART_BATCH_KEYWORDS)


def is_sports_batch(batch_name: str) -> bool:
    return any(kw in str(batch_name) for kw in SPORTS_BATCH_KEYWORDS)


def is_art_or_sports_batch(batch_name: str) -> bool:
    return is_art_batch(batch_name) or is_sports_batch(batch_name)


def infer_category(batch_name: str) -> str:
    if is_sports_batch(batch_name):
        return '体育类'
    if is_art_batch(batch_name):
        return '艺术类'
    return ''


def infer_batch_level(batch_name: str) -> str:
    if '专科' in str(batch_name):
        return '专科'
    return '本科'


def infer_formula_id(category: str, batch_level: str) -> int:
    """默认公式：河南艺术本科⑤，体育本科③，专科统一⑤/③"""
    if category == '艺术类':
        return ART_DEFAULT_FORMULA_ID
    if category == '体育类':
        return SPORTS_DEFAULT_FORMULA_ID
    return ART_DEFAULT_FORMULA_ID


def parse_optional_float(value: Any) -> float | None:
    if value is None or value == '' or value == '-':
        return None
    try:
        return round(float(str(value).strip()), 2)
    except (ValueError, TypeError):
        return None


# ── 核心采集逻辑 ────────────────────────────────────────────

def extract_art_sports_rows(
    school_id: str,
    school_name: str,
    year: int,
    province_name: str,
    province_id: str,
) -> list[dict[str, Any]]:
    """
    从 API 拉取单所学校的数据，筛选出艺术/体育批次记录，
    转换为 art_sports_admissions 表格式。
    """
    items = fetch_school_scores(school_id, year, province_id)
    rows: list[dict[str, Any]] = []

    for item in items:
        batch_name = str(item.get('local_batch_name') or '')
        if not is_art_or_sports_batch(batch_name):
            continue

        category = infer_category(batch_name)
        batch_level = infer_batch_level(batch_name)
        major_name = str(item.get('spname') or '').strip()
        if not major_name:
            continue

        composite_score = parse_optional_float(item.get('min'))
        if composite_score is None:
            continue

        # 综合分合理性校验：艺术类通常在 350~580，体育类 500~700
        if category == '艺术类' and not (200 < composite_score < 800):
            continue
        if category == '体育类' and not (300 < composite_score < 900):
            continue

        formula_id = infer_formula_id(category, batch_level)
        city = ''  # API item 中没有直接的城市字段，后期可用 LLM 补全

        rows.append({
            'province': province_name,
            'category': category,
            'batch_level': batch_level,
            'school_name': school_name,
            'major_name': major_name,
            'formula_id': formula_id,
            f'min_composite_{year}': composite_score,
            'city': city,
            'source_school_id': school_id,
            'source_batch': batch_name,
        })

    return rows


def _merge_yearly_rows(all_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    将多年数据按 (school_name, major_name, formula_id) 合并，
    使每条记录包含多年综合分。
    """
    merged: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in all_rows:
        key = (row['school_name'], row['major_name'], row['formula_id'])
        if key not in merged:
            merged[key] = {
                'province': row['province'],
                'category': row['category'],
                'batch_level': row['batch_level'],
                'school_name': row['school_name'],
                'major_name': row['major_name'],
                'formula_id': row['formula_id'],
                'min_composite_2025': None,
                'min_composite_2024': None,
                'min_composite_2023': None,
                'city': row.get('city') or '',
            }
        entry = merged[key]
        for year_field in ('min_composite_2025', 'min_composite_2024', 'min_composite_2023'):
            year_val = row.get(year_field)
            if year_val is not None:
                entry[year_field] = year_val
        if row.get('city') and not entry['city']:
            entry['city'] = row['city']
    return list(merged.values())


# ── LLM 辅助：公式推断与城市补全 ──────────────────────────

def is_llm_available() -> bool:
    settings = get_llm_settings()
    return bool(settings and settings.get('is_enabled') and settings.get('api_key') and settings.get('model_name'))


def enrich_with_llm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    使用 LLM 对采集数据进行增强：
    - 推断正确的 formula_id（不同学校可能用不同公式）
    - 补全城市信息
    - 剔除明显异常的数据

    如 LLM 不可用则直接返回原数据。
    """
    if not rows or not is_llm_available():
        return rows

    # 分批处理，每批最多 50 条
    batch_size = 50
    enriched: list[dict[str, Any]] = []

    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        try:
            result = _llm_enrich_batch(batch)
            enriched.extend(result)
        except Exception:
            # LLM 失败则保留原数据
            enriched.extend(batch)

    return enriched


def _llm_enrich_batch(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """LLM 增强单批数据。"""
    items_text = json.dumps([
        {
            'school_name': r['school_name'],
            'major_name': r['major_name'],
            'category': r['category'],
            'batch_level': r['batch_level'],
            'min_composite_2025': r.get('min_composite_2025'),
            'current_formula_id': r['formula_id'],
        }
        for r in rows
    ], ensure_ascii=False, indent=2)

    prompt = f"""请对以下河南省艺术类/体育类院校录取数据进行校验和增强。

数据：
{items_text}

任务：
1. 确认 formula_id 是否正确。河南省艺术本科默认公式⑤（0.5W+1.25Z），但部分院校可能使用其他公式。
   如果你从院校名称能判断其公式编号，请修正；否则保持默认值。
   公式参考：①仅文化 ②0.8W+0.5Z ③0.7W+0.75Z ④0.6W+Z ⑤0.5W+1.25Z
2. 补全 city 字段（学校所在城市）
3. 如果某条记录的 min_composite_2025 明显不合理（如不在 250~750 范围），标记 remove=true

返回 JSON：
{{"items":[{{"index":0,"formula_id":5,"city":"郑州"}}]}}
不要输出 markdown 代码块。"""

    content = chat_completion(
        [{'role': 'user', 'content': prompt}],
        max_tokens=4096,
    )

    # 解析 LLM 响应
    cleaned = str(content or '').strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]

    try:
        payload = json.loads(cleaned)
        updates = payload.get('items') if isinstance(payload, dict) else payload
    except json.JSONDecodeError:
        return rows

    if not isinstance(updates, list):
        return rows

    update_map: dict[int, dict[str, Any]] = {}
    for upd in updates:
        if isinstance(upd, dict) and 'index' in upd:
            update_map[int(upd['index'])] = upd

    result: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        upd = update_map.get(idx, {})
        if upd.get('remove'):
            continue
        if upd.get('formula_id') and 1 <= int(upd['formula_id']) <= 5:
            row['formula_id'] = int(upd['formula_id'])
        if upd.get('city') and not row.get('city'):
            row['city'] = str(upd['city']).strip()
        result.append(row)

    return result


# ── 数据库存储 ──────────────────────────────────────────────

def store_art_sports_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    """将采集数据写入 art_sports_admissions 表（upsert）。"""
    from henan_art_sports_service import ensure_art_sports_admissions_table
    ensure_art_sports_admissions_table()
    success = 0
    fail = 0

    with get_connection() as connection:
        for row in rows:
            try:
                connection.execute(
                    '''
                    INSERT INTO art_sports_admissions (
                      province, category, batch_level, school_name, major_name, formula_id,
                      min_composite_2025, min_composite_2024, min_composite_2023, city
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(province, category, batch_level, school_name, major_name, formula_id) DO UPDATE SET
                      min_composite_2025 = COALESCE(excluded.min_composite_2025, art_sports_admissions.min_composite_2025),
                      min_composite_2024 = COALESCE(excluded.min_composite_2024, art_sports_admissions.min_composite_2024),
                      min_composite_2023 = COALESCE(excluded.min_composite_2023, art_sports_admissions.min_composite_2023),
                      city = COALESCE(NULLIF(excluded.city, ''), art_sports_admissions.city)
                    ''',
                    [
                        row['province'],
                        row['category'],
                        row['batch_level'],
                        row['school_name'],
                        row['major_name'],
                        int(row['formula_id']),
                        row.get('min_composite_2025'),
                        row.get('min_composite_2024'),
                        row.get('min_composite_2023'),
                        row.get('city') or '',
                    ],
                )
                success += 1
            except Exception:
                fail += 1
        connection.commit()

    return {'success': success, 'fail': fail}


# ── 采集任务编排 ────────────────────────────────────────────

def get_art_school_ids(province: str) -> list[tuple[str, str]]:
    """
    获取指定省份所有开设艺术/体育类专业的院校列表。
    返回 [(school_id, school_name), ...]
    """
    schools = fetch_school_list()
    result: list[tuple[str, str]] = []
    for sid, info in schools.items():
        p = str(info.get('p') or '')
        if province not in p:
            continue
        # 包含艺术/体育/美术/音乐/设计/传媒等关键词，或者是综合性大学（可能有艺体专业）
        name = str(info.get('name') or '')
        # 不预先过滤，全部采集（因为很多综合大学也有艺术专业）
        result.append((sid, name))
    return result


def run_art_crawl(
    province: str = '河南',
    years: list[int] | None = None,
    school_limit: int | None = None,
    use_llm_enrich: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """
    执行艺术/体育类录取数据采集。

    参数：
    - province: 生源省份，默认河南
    - years: 采集年份列表，默认 [2025, 2024, 2023]
    - school_limit: 限制采集院校数（None=全部）
    - use_llm_enrich: 是否使用 LLM 增强数据
    - on_progress: 进度回调 (done, total, school_name)
    """
    from crawler_config import PROVINCE_IDS

    province_id = PROVINCE_IDS.get(province)
    if not province_id:
        raise ValueError(f'不支持的省份：{province}')

    if years is None:
        years = [2025, 2024, 2023]
    years = sorted(set(years), reverse=True)

    log_progress(f'开始采集 {province} 艺术/体育类录取数据')
    log_progress(f'年份：{", ".join(str(y) for y in years)}')

    # 获取院校列表
    school_entries = get_art_school_ids(province)
    if school_limit:
        school_entries = school_entries[:school_limit]

    log_progress(f'共 {len(school_entries)} 所院校待采集')

    all_rows: list[dict[str, Any]] = []
    processed = 0
    errors: list[str] = []

    for sid, sname in school_entries:
        if on_progress:
            on_progress(processed, len(school_entries), sname)

        for year in years:
            try:
                rows = extract_art_sports_rows(sid, sname, year, province, province_id)
                all_rows.extend(rows)
            except Exception as exc:
                errors.append(f'{sname}({sid}) {year}: {exc}')

        processed += 1
        time.sleep(REQUEST_INTERVAL)

        if processed % 10 == 0 or processed == len(school_entries):
            log_progress(f'[{processed}/{len(school_entries)}] {sname} — 累计 {len(all_rows)} 条')

    log_progress(f'采集完成：共 {len(all_rows)} 条原始记录，{len(errors)} 个错误')

    # 合并多年数据
    merged = _merge_yearly_rows(all_rows)
    log_progress(f'合并后 {len(merged)} 条唯一（院校+专业+公式）')

    # LLM 增强
    if use_llm_enrich and is_llm_available():
        log_progress('正在使用 LLM 增强数据...')
        enriched = enrich_with_llm(merged)
        log_progress(f'LLM 增强完成：{len(merged)} → {len(enriched)} 条')
    else:
        enriched = merged
        if use_llm_enrich:
            log_progress('LLM 未启用，跳过增强步骤')

    # 入库
    result = store_art_sports_rows(enriched)
    log_progress(f'入库完成：成功 {result["success"]}，失败 {result["fail"]}')

    # 统计各类别
    stats: dict[str, dict[str, int]] = {}
    for row in enriched:
        cat = row['category']
        bl = row['batch_level']
        if cat not in stats:
            stats[cat] = {}
        stats[cat][bl] = stats[cat].get(bl, 0) + 1

    return {
        'province': province,
        'years': years,
        'schools_processed': processed,
        'total_raw': len(all_rows),
        'total_merged': len(merged),
        'total_stored': result['success'],
        'store_failed': result['fail'],
        'llm_enriched': use_llm_enrich and is_llm_available(),
        'by_category': stats,
        'errors': errors[:20],
    }


def get_art_admission_stats() -> dict[str, Any]:
    """获取 art_sports_admissions 表的统计信息。"""
    from henan_art_sports_service import ensure_art_sports_admissions_table
    ensure_art_sports_admissions_table()
    with get_connection() as connection:
        total = connection.execute('SELECT COUNT(*) AS cnt FROM art_sports_admissions').fetchone()['cnt']
        by_category = rows_to_dicts(connection.execute(
            '''SELECT category, batch_level, COUNT(*) AS cnt
               FROM art_sports_admissions
               GROUP BY category, batch_level
               ORDER BY category, batch_level'''
        ).fetchall())
        year_coverage = {
            'has_2025': connection.execute(
                'SELECT COUNT(*) AS cnt FROM art_sports_admissions WHERE min_composite_2025 IS NOT NULL'
            ).fetchone()['cnt'],
            'has_2024': connection.execute(
                'SELECT COUNT(*) AS cnt FROM art_sports_admissions WHERE min_composite_2024 IS NOT NULL'
            ).fetchone()['cnt'],
            'has_2023': connection.execute(
                'SELECT COUNT(*) AS cnt FROM art_sports_admissions WHERE min_composite_2023 IS NOT NULL'
            ).fetchone()['cnt'],
        }
    return {
        'total_records': total,
        'by_category': by_category,
        'year_coverage': year_coverage,
    }


def clear_art_sports_admissions(province: str = '河南') -> int:
    """清空指定省份的艺术/体育录取数据。"""
    from henan_art_sports_service import ensure_art_sports_admissions_table
    ensure_art_sports_admissions_table()
    with get_connection() as connection:
        cursor = connection.execute(
            'DELETE FROM art_sports_admissions WHERE province = ?', [province]
        )
        connection.commit()
        return cursor.rowcount


# ── 后台任务包装 ────────────────────────────────────────────

def _background_art_crawl(province: str, years: list[int] | None, limit: int | None, enrich: bool) -> None:
    try:
        run_art_crawl(province=province, years=years, school_limit=limit, use_llm_enrich=enrich)
    except Exception as exc:
        log_progress(f'艺术类采集失败：{exc}')


# ── CLI ──────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    parser = argparse.ArgumentParser(description='采集艺术类/体育类录取数据')
    parser.add_argument('--province', default='河南', help='生源省份')
    parser.add_argument('--years', default='2025,2024,2023', help='年份，逗号分隔')
    parser.add_argument('--limit', type=int, default=0, help='限制院校数，0=全部')
    parser.add_argument('--no-llm', action='store_true', help='禁用 LLM 增强')
    parser.add_argument('--stats', action='store_true', help='仅显示统计')
    parser.add_argument('--clear', action='store_true', help='清空数据')
    args = parser.parse_args()

    if args.stats:
        stats = get_art_admission_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        raise SystemExit(0)

    if args.clear:
        count = clear_art_sports_admissions(args.province)
        print(f'已清空 {args.province} 的 {count} 条艺术/体育数据')
        raise SystemExit(0)

    years = [int(y.strip()) for y in args.years.split(',') if y.strip()]
    limit = None if args.limit == 0 else args.limit

    def progress(done: int, total: int, name: str) -> None:
        log_progress(f'[{done}/{total}] {name}')

    result = run_art_crawl(
        province=args.province,
        years=years,
        school_limit=limit,
        use_llm_enrich=not args.no_llm,
        on_progress=progress,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
