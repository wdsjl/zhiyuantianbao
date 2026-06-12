import csv
import io
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from db import get_connection, row_to_dict

REQUIRED_HEADERS = ['年份', '省份', '批次', '院校代码', '院校名称', '专业代码', '专业名称']

HEADER_MAP = {
    '年份': 'year',
    '省份': 'province',
    '批次': 'batch',
    '院校代码': 'school_code',
    '院校名称': 'school_name',
    '院校所在省': 'school_province',
    '城市': 'city',
    '院校类型': 'school_type',
    '办学层次': 'education_level',
    '是否985': 'is_985',
    '是否211': 'is_211',
    '是否双一流': 'is_double_first_class',
    '是否公办': 'is_public',
    '专业代码': 'major_code',
    '专业名称': 'major_name',
    '专业门类': 'major_category',
    '专业类型': 'major_type',
    '学历层次': 'degree_type',
    '学制': 'duration',
    '选科要求': 'subject_requirement',
    '招生人数': 'enrollment_count',
    '学费': 'tuition',
    '校区': 'campus',
    '特殊说明': 'special_notes',
    '最低分': 'min_score',
    '最低位次': 'min_rank',
    '平均分': 'avg_score',
    '平均位次': 'avg_rank',
    '最高分': 'max_score',
    '最高位次': 'max_rank'
}

INT_FIELDS = {
    'year', 'is_985', 'is_211', 'is_double_first_class', 'is_public',
    'enrollment_count', 'tuition', 'min_score', 'min_rank', 'avg_score',
    'avg_rank', 'max_score', 'max_rank'
}


def normalize_bool(value: Any, default: int = 0) -> int:
    if value is None or value == '':
        return default
    text = str(value).strip().lower()
    if text in ['1', '是', 'true', 'yes', 'y', '公办', '双一流', '985', '211']:
        return 1
    if text in ['0', '否', 'false', 'no', 'n', '民办']:
        return 0
    return default


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == '':
        return default
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return default


def normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
    row = {}
    for cn_key, value in raw.items():
        if cn_key is None:
            continue
        key = HEADER_MAP.get(str(cn_key).strip())
        if not key:
            continue
        if isinstance(value, str):
            value = value.strip()
        row[key] = value

    for field in INT_FIELDS:
        if field in row:
            if field in ['is_985', 'is_211', 'is_double_first_class', 'is_public']:
                row[field] = normalize_bool(row[field], default=1 if field == 'is_public' else 0)
            else:
                row[field] = to_int(row[field])

    row.setdefault('school_province', row.get('province'))
    row.setdefault('city', '')
    row.setdefault('school_type', '')
    row.setdefault('education_level', '本科')
    row.setdefault('is_985', 0)
    row.setdefault('is_211', 0)
    row.setdefault('is_double_first_class', 0)
    row.setdefault('is_public', 1)
    row.setdefault('major_category', '')
    row.setdefault('major_type', '')
    row.setdefault('degree_type', '本科')
    row.setdefault('duration', '')
    return row


def validate_headers(headers: list[str]) -> None:
    missing = [header for header in REQUIRED_HEADERS if header not in headers]
    if missing:
        raise ValueError(f'缺少必填字段：{", ".join(missing)}')


def parse_xlsx(content: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    worksheet = workbook.active
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(cell).strip() if cell is not None else '' for cell in rows[0]]
    validate_headers(headers)
    result = []
    for values in rows[1:]:
        if not any(values):
            continue
        raw = {headers[index]: values[index] if index < len(values) else None for index in range(len(headers))}
        result.append(normalize_row(raw))
    return result


def parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    validate_headers(headers)
    return [normalize_row(row) for row in reader]


def parse_import_file(filename: str, content: bytes) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == '.xlsx':
        return parse_xlsx(content)
    if suffix == '.csv':
        return parse_csv(content)
    raise ValueError('仅支持 .xlsx 或 .csv 文件')


def get_or_create_school(connection, row: dict[str, Any]) -> int:
    school = row_to_dict(connection.execute('SELECT school_id FROM schools WHERE school_code = ?', [row['school_code']]).fetchone())
    if school:
        connection.execute(
            '''
            UPDATE schools SET school_name = ?, province = ?, city = ?, school_type = ?, education_level = ?,
              is_985 = ?, is_211 = ?, is_double_first_class = ?, is_public = ?, updated_at = CURRENT_TIMESTAMP
            WHERE school_id = ?
            ''',
            [
                row['school_name'], row.get('school_province'), row.get('city'), row.get('school_type'),
                row.get('education_level'), row.get('is_985'), row.get('is_211'), row.get('is_double_first_class'),
                row.get('is_public'), school['school_id']
            ]
        )
        return school['school_id']

    cursor = connection.execute(
        '''
        INSERT INTO schools (school_code, school_name, province, city, school_type, education_level, is_985, is_211, is_double_first_class, is_public)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [
            row['school_code'], row['school_name'], row.get('school_province'), row.get('city'), row.get('school_type'),
            row.get('education_level'), row.get('is_985'), row.get('is_211'), row.get('is_double_first_class'), row.get('is_public')
        ]
    )
    return cursor.lastrowid


def get_or_create_major(connection, row: dict[str, Any]) -> int:
    major = row_to_dict(connection.execute('SELECT major_id FROM majors WHERE major_code = ?', [row['major_code']]).fetchone())
    if major:
        connection.execute(
            '''
            UPDATE majors SET major_name = ?, major_category = ?, major_type = ?, degree_type = ?, duration = ?, updated_at = CURRENT_TIMESTAMP
            WHERE major_id = ?
            ''',
            [row['major_name'], row.get('major_category'), row.get('major_type'), row.get('degree_type'), row.get('duration'), major['major_id']]
        )
        return major['major_id']

    cursor = connection.execute(
        '''
        INSERT INTO majors (major_code, major_name, major_category, major_type, degree_type, duration)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        [row['major_code'], row['major_name'], row.get('major_category'), row.get('major_type'), row.get('degree_type'), row.get('duration')]
    )
    return cursor.lastrowid


def upsert_plan(connection, row: dict[str, Any], school_id: int, major_id: int) -> None:
    connection.execute(
        '''
        INSERT INTO enrollment_plans (
          year, province, batch, school_id, school_code, major_id, major_code, major_name,
          subject_requirement, enrollment_count, tuition, duration, campus, special_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(year, province, batch, school_id, major_id) DO UPDATE SET
          subject_requirement = excluded.subject_requirement,
          enrollment_count = excluded.enrollment_count,
          tuition = excluded.tuition,
          duration = excluded.duration,
          campus = excluded.campus,
          special_notes = excluded.special_notes,
          updated_at = CURRENT_TIMESTAMP
        ''',
        [
            row['year'], row['province'], row['batch'], school_id, row['school_code'], major_id, row['major_code'], row['major_name'],
            row.get('subject_requirement'), row.get('enrollment_count'), row.get('tuition'), row.get('duration'), row.get('campus'), row.get('special_notes')
        ]
    )


def upsert_admission(connection, row: dict[str, Any], school_id: int, major_id: int) -> None:
    connection.execute(
        '''
        INSERT INTO admission_records (
          year, province, batch, school_id, school_code, major_id, major_code,
          min_score, min_rank, avg_score, avg_rank, max_score, max_rank, enrollment_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(year, province, batch, school_id, major_id) DO UPDATE SET
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
            row.get('min_score'), row.get('min_rank'), row.get('avg_score'), row.get('avg_rank'), row.get('max_score'), row.get('max_rank'), row.get('enrollment_count')
        ]
    )


def insert_import_log(connection, import_type: str, file_name: str, total_count: int, success_count: int, fail_count: int, error_message: str | None) -> int:
    cursor = connection.execute(
        '''
        INSERT INTO import_logs (import_type, file_name, total_count, success_count, fail_count, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        [import_type, file_name, total_count, success_count, fail_count, error_message]
    )
    return cursor.lastrowid


def import_plan_rows(filename: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            'log_id': None,
            'total_count': 0,
            'success_count': 0,
            'fail_count': 0,
            'errors': [],
        }
    success_count = 0
    errors: list[str] = []

    with get_connection() as connection:
        for index, row in enumerate(rows, start=2):
            try:
                for field in ['year', 'province', 'batch', 'school_code', 'school_name', 'major_code', 'major_name']:
                    if not row.get(field):
                        raise ValueError(f'第 {index} 行缺少字段：{field}')
                school_id = get_or_create_school(connection, row)
                major_id = get_or_create_major(connection, row)
                upsert_plan(connection, row, school_id, major_id)
                success_count += 1
            except Exception as exc:
                errors.append(str(exc))

        fail_count = len(errors)
        error_message = '\n'.join(errors[:20]) if errors else None
        log_id = insert_import_log(connection, 'enrollment_plans', filename, len(rows), success_count, fail_count, error_message)
        connection.commit()

    return {
        'log_id': log_id,
        'total_count': len(rows),
        'success_count': success_count,
        'fail_count': fail_count,
        'errors': errors[:20],
    }


def import_admission_rows(filename: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    success_count = 0
    errors = []

    with get_connection() as connection:
        for index, row in enumerate(rows, start=2):
            try:
                for field in ['year', 'province', 'batch', 'school_code', 'school_name', 'major_code', 'major_name']:
                    if not row.get(field):
                        raise ValueError(f'第 {index} 行缺少字段：{field}')
                school_id = get_or_create_school(connection, row)
                major_id = get_or_create_major(connection, row)
                upsert_plan(connection, row, school_id, major_id)
                upsert_admission(connection, row, school_id, major_id)
                success_count += 1
            except Exception as exc:
                errors.append(str(exc))

        fail_count = len(errors)
        error_message = '\n'.join(errors[:20]) if errors else None
        log_id = insert_import_log(connection, 'admission_records', filename, len(rows), success_count, fail_count, error_message)
        connection.commit()

    return {
        'log_id': log_id,
        'total_count': len(rows),
        'success_count': success_count,
        'fail_count': fail_count,
        'errors': errors[:20]
    }
