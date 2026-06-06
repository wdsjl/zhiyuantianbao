"""
将本地爬取完成的 SQLite 数据库中的「高考基础数据」合并到服务器数据库。

只合并：schools、majors、admission_records、enrollment_plans、import_logs、crawl_logs
不会覆盖：users、students、订单、会员、志愿草稿等业务数据。

用法：
  python db_merge.py --source D:/backup/zhiyuan_local.db
  python db_merge.py --source D:/backup/zhiyuan_local.db --target C:/zhiyuantianbao/database/zhiyuan.db
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from db import DB_PATH

DATA_TABLES = [
    'schools',
    'majors',
    'admission_records',
    'enrollment_plans',
    'import_logs',
    'crawl_logs',
]


def connect_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON;')
    return connection


def table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = connection.execute(f'PRAGMA table_info({table})').fetchall()
    return [row['name'] for row in rows]


def upsert_schools(source: sqlite3.Connection, target: sqlite3.Connection) -> dict[int, int]:
    mapping: dict[int, int] = {}
    columns = [name for name in table_columns(source, 'schools') if name != 'school_id']
    for row in source.execute('SELECT * FROM schools').fetchall():
        data = {key: row[key] for key in columns}
        existing = target.execute(
            'SELECT school_id FROM schools WHERE school_code = ?',
            [data['school_code']]
        ).fetchone()
        if existing:
            school_id = existing['school_id']
            assignments = ', '.join(f'{key} = ?' for key in columns if key not in ['created_at'])
            values = [data[key] for key in columns if key not in ['created_at']] + [school_id]
            target.execute(
                f'UPDATE schools SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE school_id = ?',
                values
            )
        else:
            placeholders = ', '.join(['?'] * len(columns))
            cursor = target.execute(
                f'INSERT INTO schools ({", ".join(columns)}) VALUES ({placeholders})',
                [data[key] for key in columns]
            )
            school_id = cursor.lastrowid
        mapping[row['school_id']] = school_id
    return mapping


def upsert_majors(source: sqlite3.Connection, target: sqlite3.Connection) -> dict[int, int]:
    mapping: dict[int, int] = {}
    columns = [name for name in table_columns(source, 'majors') if name != 'major_id']
    for row in source.execute('SELECT * FROM majors').fetchall():
        data = {key: row[key] for key in columns}
        existing = target.execute(
            'SELECT major_id FROM majors WHERE major_code = ?',
            [data['major_code']]
        ).fetchone()
        if existing:
            major_id = existing['major_id']
            assignments = ', '.join(f'{key} = ?' for key in columns if key not in ['created_at'])
            values = [data[key] for key in columns if key not in ['created_at']] + [major_id]
            target.execute(
                f'UPDATE majors SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE major_id = ?',
                values
            )
        else:
            placeholders = ', '.join(['?'] * len(columns))
            cursor = target.execute(
                f'INSERT INTO majors ({", ".join(columns)}) VALUES ({placeholders})',
                [data[key] for key in columns]
            )
            major_id = cursor.lastrowid
        mapping[row['major_id']] = major_id
    return mapping


def upsert_admissions(source: sqlite3.Connection, target: sqlite3.Connection, school_map: dict[int, int], major_map: dict[int, int]) -> int:
    count = 0
    for row in source.execute('SELECT * FROM admission_records').fetchall():
        school_id = school_map.get(row['school_id'])
        major_id = major_map.get(row['major_id'])
        if not school_id or not major_id:
            continue
        target.execute(
            '''
            INSERT INTO admission_records (
              year, province, batch, school_id, school_code, major_id, major_code,
              min_score, min_rank, avg_score, avg_rank, max_score, max_rank, enrollment_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(year, province, batch, school_id, major_id) DO UPDATE SET
              school_code = excluded.school_code,
              major_code = excluded.major_code,
              min_score = excluded.min_score,
              min_rank = excluded.min_rank,
              avg_score = excluded.avg_score,
              avg_rank = excluded.avg_rank,
              max_score = excluded.max_score,
              max_rank = excluded.max_rank,
              enrollment_count = excluded.enrollment_count,
              updated_at = CURRENT_TIMESTAMP
            ''',
            [
                row['year'], row['province'], row['batch'], school_id, row['school_code'], major_id, row['major_code'],
                row['min_score'], row['min_rank'], row['avg_score'], row['avg_rank'], row['max_score'], row['max_rank'],
                row['enrollment_count']
            ]
        )
        count += 1
    return count


def upsert_plans(source: sqlite3.Connection, target: sqlite3.Connection, school_map: dict[int, int], major_map: dict[int, int]) -> int:
    count = 0
    for row in source.execute('SELECT * FROM enrollment_plans').fetchall():
        school_id = school_map.get(row['school_id'])
        major_id = major_map.get(row['major_id'])
        if not school_id or not major_id:
            continue
        target.execute(
            '''
            INSERT INTO enrollment_plans (
              year, province, batch, school_id, school_code, major_id, major_code, major_name,
              subject_requirement, enrollment_count, tuition, duration, campus, special_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(year, province, batch, school_id, major_id) DO UPDATE SET
              school_code = excluded.school_code,
              major_code = excluded.major_code,
              major_name = excluded.major_name,
              subject_requirement = excluded.subject_requirement,
              enrollment_count = excluded.enrollment_count,
              tuition = excluded.tuition,
              duration = excluded.duration,
              campus = excluded.campus,
              special_notes = excluded.special_notes,
              updated_at = CURRENT_TIMESTAMP
            ''',
            [
                row['year'], row['province'], row['batch'], school_id, row['school_code'], major_id, row['major_code'],
                row['major_name'], row['subject_requirement'], row['enrollment_count'], row['tuition'], row['duration'],
                row['campus'], row['special_notes']
            ]
        )
        count += 1
    return count


def copy_logs(source: sqlite3.Connection, target: sqlite3.Connection, table: str) -> int:
    if table not in {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
        return 0
    columns = table_columns(source, table)
    insert_columns = [name for name in columns if name not in [f'{table[:-1]}_id' if table.endswith('s') else 'id']]
    # import_logs: log_id, crawl_logs: crawl_id - skip auto id
    skip_id = 'log_id' if table == 'import_logs' else 'crawl_id' if table == 'crawl_logs' else None
    if not skip_id:
        return 0
    write_columns = [name for name in columns if name != skip_id]
    count = 0
    for row in source.execute(f'SELECT * FROM {table}').fetchall():
        target.execute(
            f'INSERT INTO {table} ({", ".join(write_columns)}) VALUES ({", ".join(["?"] * len(write_columns))})',
            [row[name] for name in write_columns]
        )
        count += 1
    return count


def merge_database(source_path: Path, target_path: Path) -> dict[str, int | str]:
    if not source_path.exists():
        raise FileNotFoundError(f'源数据库不存在：{source_path}')
    if not target_path.exists():
        raise FileNotFoundError(f'目标数据库不存在：{target_path}')

    source = connect_db(source_path)
    target = connect_db(target_path)
    try:
        school_map = upsert_schools(source, target)
        major_map = upsert_majors(source, target)
        admission_count = upsert_admissions(source, target, school_map, major_map)
        plan_count = upsert_plans(source, target, school_map, major_map)
        import_log_count = copy_logs(source, target, 'import_logs')
        crawl_log_count = copy_logs(source, target, 'crawl_logs')
        target.commit()
        return {
            'schools': len(school_map),
            'majors': len(major_map),
            'admissions': admission_count,
            'plans': plan_count,
            'import_logs': import_log_count,
            'crawl_logs': crawl_log_count,
            'source': str(source_path),
            'target': str(target_path),
        }
    finally:
        source.close()
        target.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='合并本地爬取数据库到服务器数据库')
    parser.add_argument('--source', required=True, help='本地爬取完成的数据库路径，如 D:/data/zhiyuan_local.db')
    parser.add_argument('--target', default=str(DB_PATH), help='服务器目标数据库，默认项目 database/zhiyuan.db')
    args = parser.parse_args()
    result = merge_database(Path(args.source), Path(args.target))
    print('合并完成：')
    for key, value in result.items():
        print(f'  {key}: {value}')
