"""院校库：按招生省份查询院校列表与分数/计划快照。"""

from __future__ import annotations

from typing import Any

from db import get_connection, rows_to_dicts
from recommend_service import expand_batch_aliases, province_variants


def _province_batch_filters(
    province: str,
    batch: str,
    *,
    table_alias: str,
) -> tuple[str, list[Any]]:
    variants = province_variants(province)
    province_placeholders = ','.join(['?'] * len(variants))
    params: list[Any] = [*variants]
    batch_clause = ''
    if batch:
        batch_aliases = expand_batch_aliases(batch) or [batch]
        batch_placeholders = ','.join(['?'] * len(batch_aliases))
        batch_clause = f' AND {table_alias}.batch IN ({batch_placeholders})'
        params.extend(batch_aliases)
    province_clause = f'{table_alias}.province IN ({province_placeholders})'
    return f'{province_clause}{batch_clause}', params


def query_province_school_ids(
    province: str,
    batch: str = '',
) -> set[int]:
    if not province:
        return set()
    plan_clause, plan_params = _province_batch_filters(province, batch, table_alias='ep')
    admission_clause, admission_params = _province_batch_filters(province, batch, table_alias='ar')
    sql = f'''
    SELECT school_id FROM enrollment_plans ep WHERE {plan_clause}
    UNION
    SELECT school_id FROM admission_records ar WHERE {admission_clause}
    '''
    with get_connection() as connection:
        rows = connection.execute(sql, [*plan_params, *admission_params]).fetchall()
    return {int(row['school_id']) for row in rows if row['school_id'] is not None}


def list_province_schools(
    province: str,
    batch: str = '',
    *,
    keyword: str = '',
    city: str = '',
    is_public: int | None = None,
    is_double_first_class: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    province = (province or '').strip()
    if not province:
        return list_all_schools(
            keyword=keyword,
            city=city,
            is_public=is_public,
            is_double_first_class=is_double_first_class,
            limit=limit,
            offset=offset,
        )

    school_ids = query_province_school_ids(province, batch)
    if not school_ids:
        return {'list': [], 'total': 0, 'province': province, 'batch': batch}

    placeholders = ','.join(['?'] * len(school_ids))
    sql = f'SELECT * FROM schools WHERE school_id IN ({placeholders})'
    params: list[Any] = list(school_ids)
    if keyword:
        like = f'%{keyword}%'
        sql += ' AND (school_name LIKE ? OR school_code LIKE ? OR city LIKE ?)'
        params.extend([like, like, like])
    if city:
        sql += ' AND city = ?'
        params.append(city)
    if is_public is not None:
        sql += ' AND is_public = ?'
        params.append(is_public)
    if is_double_first_class is not None:
        sql += ' AND is_double_first_class = ?'
        params.append(is_double_first_class)

    count_sql = f'SELECT COUNT(*) AS total FROM ({sql})'
    sql += ' ORDER BY is_985 DESC, is_211 DESC, is_double_first_class DESC, school_name ASC LIMIT ? OFFSET ?'
    params_with_page = [*params, max(1, min(int(limit), 2000)), max(0, int(offset))]

    with get_connection() as connection:
        total = int(connection.execute(count_sql, params).fetchone()['total'])
        rows = rows_to_dicts(connection.execute(sql, params_with_page).fetchall())
    return {'list': rows, 'total': total, 'province': province, 'batch': batch}


def list_all_schools(
    *,
    keyword: str = '',
    city: str = '',
    is_public: int | None = None,
    is_double_first_class: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    sql = 'SELECT * FROM schools WHERE 1=1'
    params: list[Any] = []
    if keyword:
        like = f'%{keyword}%'
        sql += ' AND (school_name LIKE ? OR school_code LIKE ? OR city LIKE ?)'
        params.extend([like, like, like])
    if city:
        sql += ' AND city = ?'
        params.append(city)
    if is_public is not None:
        sql += ' AND is_public = ?'
        params.append(is_public)
    if is_double_first_class is not None:
        sql += ' AND is_double_first_class = ?'
        params.append(is_double_first_class)

    count_sql = f'SELECT COUNT(*) AS total FROM ({sql})'
    sql += ' ORDER BY is_985 DESC, is_211 DESC, is_double_first_class DESC, school_id ASC LIMIT ? OFFSET ?'
    page_params = [*params, max(1, min(int(limit), 2000)), max(0, int(offset))]

    with get_connection() as connection:
        total = int(connection.execute(count_sql, params).fetchone()['total'])
        rows = rows_to_dicts(connection.execute(sql, page_params).fetchall())
    return {'list': rows, 'total': total}


def build_school_snapshot_map(
    province: str,
    batch: str = '',
    year: int | None = None,
    keyword: str = '',
    limit: int = 5000,
) -> dict[int, dict[str, Any]]:
    variants = province_variants(province)
    province_placeholders = ','.join(['?'] * len(variants))
    batch_aliases = expand_batch_aliases(batch) or [batch] if batch else []
    batch_placeholders = ','.join(['?'] * len(batch_aliases)) if batch_aliases else ''
    snapshot: dict[int, dict[str, Any]] = {}

    admission_sql = f'''
    SELECT
      ar.school_id,
      MIN(ar.min_rank) AS best_min_rank,
      MIN(ar.min_score) AS best_min_score,
      COUNT(DISTINCT ar.major_id) AS major_count,
      MAX(ar.year) AS latest_year
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    WHERE ar.province IN ({province_placeholders})
    '''
    admission_params: list[Any] = [*variants]
    if batch_aliases:
        admission_sql += f' AND ar.batch IN ({batch_placeholders})'
        admission_params.extend(batch_aliases)
    if year is not None:
        admission_sql += ' AND ar.year = ?'
        admission_params.append(year)
    if keyword:
        like = f'%{keyword}%'
        admission_sql += ' AND (s.school_name LIKE ? OR s.school_code LIKE ?)'
        admission_params.extend([like, like])
    admission_sql += ' GROUP BY ar.school_id'

    plan_sql = f'''
    SELECT
      ep.school_id,
      COUNT(DISTINCT ep.major_id) AS plan_major_count,
      MAX(ep.year) AS latest_plan_year
    FROM enrollment_plans ep
    JOIN schools s ON s.school_id = ep.school_id
    WHERE ep.province IN ({province_placeholders})
    '''
    plan_params: list[Any] = [*variants]
    if batch_aliases:
        plan_sql += f' AND ep.batch IN ({batch_placeholders})'
        plan_params.extend(batch_aliases)
    if year is not None:
        plan_sql += ' AND ep.year = ?'
        plan_params.append(year)
    if keyword:
        like = f'%{keyword}%'
        plan_sql += ' AND (s.school_name LIKE ? OR s.school_code LIKE ?)'
        plan_params.extend([like, like])
    plan_sql += ' GROUP BY ep.school_id'

    with get_connection() as connection:
        for row in rows_to_dicts(connection.execute(admission_sql, admission_params).fetchall()):
            school_id = int(row['school_id'])
            snapshot[school_id] = {
                'school_id': school_id,
                'best_min_rank': row.get('best_min_rank'),
                'best_min_score': row.get('best_min_score'),
                'major_count': int(row.get('major_count') or 0),
                'latest_year': row.get('latest_year'),
                'plan_major_count': 0,
            }
        for row in rows_to_dicts(connection.execute(plan_sql, plan_params).fetchall()):
            school_id = int(row['school_id'])
            existing = snapshot.setdefault(school_id, {
                'school_id': school_id,
                'best_min_rank': None,
                'best_min_score': None,
                'major_count': 0,
                'latest_year': None,
                'plan_major_count': 0,
            })
            existing['plan_major_count'] = int(row.get('plan_major_count') or 0)
            if not existing.get('latest_year'):
                existing['latest_year'] = row.get('latest_plan_year')
            if not existing.get('major_count'):
                existing['major_count'] = existing['plan_major_count']

    if limit and len(snapshot) > limit:
        trimmed = dict(list(snapshot.items())[:limit])
        return trimmed
    return snapshot
