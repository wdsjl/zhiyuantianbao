import csv
import io
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from db import get_connection, row_to_dict

REQUIRED_ALIASES: dict[str, list[str]] = {
    'year': ['年份'],
    'province': ['省份', '生源地'],
    'batch': ['批次'],
    'school_code': ['院校代码'],
    'school_name': ['院校名称'],
    'major_code': ['专业代码'],
    'major_name': ['专业名称', '专业全称'],
}

HEADER_MAP = {
    '年份': 'year',
    '省份': 'province',
    '生源地': 'province',
    '批次': 'batch',
    '科类': 'exam_subject_type',
    '批次备注': 'batch_remark',
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
    '专业全称': 'major_name',
    '专业门类': 'major_category',
    '专业类型': 'major_type',
    '学历层次': 'degree_type',
    '学制': 'duration',
    '选科要求': 'subject_requirement',
    '招生人数': 'enrollment_count',
    '计划人数': 'enrollment_count',
    '录取人数': 'enrollment_count',
    '专业录取人数': 'enrollment_count',
    '学费': 'tuition',
    '校区': 'campus',
    '特殊说明': 'special_notes',
    '最低分': 'min_score',
    '最低位次': 'min_rank',
    '专业组最低分': 'min_score',
    '专业组最低位次': 'min_rank',
    '专业最低分': 'min_score',
    '专业最低位次': 'min_rank',
    '平均分': 'avg_score',
    '平均位次': 'avg_rank',
    '最高分': 'max_score',
    '最高位次': 'max_rank',
    '保研率': 'postgraduate_rate',
    '院校保研率': 'postgraduate_rate',
    '推免率': 'postgraduate_rate',
    '官网': 'website',
    '学校官网': 'website',
    '院校官网': 'website',
    '2025招生章程': 'regulation_url',
    '2026招生章程': 'regulation_url',
    '招生章程': 'regulation_url',
    '招生章程链接': 'regulation_url',
}

INT_FIELDS = {
    'year', 'is_985', 'is_211', 'is_double_first_class', 'is_public',
    'enrollment_count', 'tuition', 'min_score', 'min_rank', 'avg_score',
    'avg_rank', 'max_score', 'max_rank', 'regulation_year'
}


def resolve_import_header(cn_key: str) -> str | None:
    key = str(cn_key or '').strip()
    if not key:
        return None
    if key in HEADER_MAP:
        return HEADER_MAP[key]
    if '招生章程' in key:
        return 'regulation_url'
    if '保研率' in key or '推免率' in key:
        return 'postgraduate_rate'
    if key in ('官网', '学校官网', '院校官网', '官方网站'):
        return 'website'
    if '专业全称' == key:
        return 'major_name'
    if '生源地' == key:
        return 'province'
    if '专业组最低分' in key or key.endswith('最低分'):
        return 'min_score'
    if '专业组最低位次' in key or key.endswith('最低位次'):
        return 'min_rank'
    return None


def find_header_row_index(rows: list[tuple[Any, ...]]) -> int:
    for idx, row in enumerate(rows[:25]):
        labels = [str(cell).strip() if cell is not None else '' for cell in row]
        if '院校名称' in labels and any(label in labels for label in ('生源地', '省份')):
            return idx
    return 0


def cell_import_value(cell: Any, header: str) -> Any:
    if cell is None:
        return None
    field = resolve_import_header(header)
    hyperlink = getattr(cell, 'hyperlink', None)
    if field == 'regulation_url' and hyperlink and getattr(hyperlink, 'target', None):
        target = str(hyperlink.target).strip()
        if target:
            return target
    value = getattr(cell, 'value', cell)
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return value


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
    from school_profile_service import infer_regulation_year, normalize_postgraduate_rate

    row = {}
    regulation_year = None
    for cn_key, value in raw.items():
        if cn_key is None:
            continue
        key = resolve_import_header(cn_key)
        if not key:
            continue
        if key == 'regulation_url':
            regulation_year = infer_regulation_year(cn_key)
        if isinstance(value, str):
            value = value.strip()
        row[key] = value

    if row.get('regulation_url') and regulation_year:
        row['regulation_year'] = regulation_year
    if row.get('postgraduate_rate'):
        row['postgraduate_rate'] = normalize_postgraduate_rate(row['postgraduate_rate'])

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
    if not row.get('province'):
        row['province'] = row.get('school_province') or '河南'
    if row.get('province'):
        row['province'] = str(row['province']).replace('省', '').strip()
    if not row.get('school_province'):
        row['school_province'] = row.get('province')
    return row


def validate_headers(headers: list[str]) -> None:
    header_set = {str(header).strip() for header in headers if header}
    missing_labels: list[str] = []
    for field, aliases in REQUIRED_ALIASES.items():
        if not any(alias in header_set for alias in aliases):
            missing_labels.append(' / '.join(aliases))
    if missing_labels:
        raise ValueError(f'缺少必填字段：{", ".join(missing_labels)}')


def parse_xlsx(content: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(content), read_only=False, data_only=False)
    worksheet = workbook.active
    matrix = list(worksheet.iter_rows(values_only=False))
    if not matrix:
        return []
    plain_rows = [tuple(cell.value for cell in row) for row in matrix]
    header_idx = find_header_row_index(plain_rows)
    header_cells = matrix[header_idx]
    headers = [str(cell.value).strip() if cell.value is not None else '' for cell in header_cells]
    validate_headers(headers)
    result = []
    for row_cells in matrix[header_idx + 1:]:
        if not any(cell.value is not None and str(cell.value).strip() != '' for cell in row_cells):
            continue
        raw = {
            headers[index]: cell_import_value(row_cells[index], headers[index])
            for index in range(min(len(headers), len(row_cells)))
            if headers[index]
        }
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


_XLSX_NS = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def _active_sheet_path(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        workbook = ET.fromstring(zf.read('xl/workbook.xml'))
        rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
        rel_map = {rel.get('Id'): rel.get('Target', '') for rel in rels}
        sheets = workbook.findall('main:sheet', _XLSX_NS)
        if not sheets:
            return 'xl/worksheets/sheet1.xml'
        rid = sheets[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        target = rel_map.get(rid, 'worksheets/sheet1.xml')
        if target.startswith('/'):
            return 'xl' + target
        if not target.startswith('xl/'):
            return 'xl/' + target
        return target


def _extract_hyperlinks_by_row(content: bytes, sheet_path: str | None = None) -> dict[int, str]:
    sheet_path = sheet_path or _active_sheet_path(content)
    rels_path = sheet_path.replace('worksheets/', 'worksheets/_rels/').replace('.xml', '.xml.rels')
    result: dict[int, str] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        if sheet_path not in zf.namelist():
            return result
        rel_targets: dict[str, str] = {}
        if rels_path in zf.namelist():
            rel_root = ET.fromstring(zf.read(rels_path))
            for rel in rel_root:
                rel_type = rel.get('Type', '')
                if 'hyperlink' in rel_type:
                    rel_targets[rel.get('Id', '')] = rel.get('Target', '')
        root = ET.fromstring(zf.read(sheet_path))
        hyperlinks = root.find('main:hyperlinks', _XLSX_NS)
        if hyperlinks is None:
            return result
        for hyperlink in hyperlinks.findall('main:hyperlink', _XLSX_NS):
            ref = hyperlink.get('ref', '')
            rid = hyperlink.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            if not ref or not rid:
                continue
            url = str(rel_targets.get(rid, '')).strip()
            if not url:
                continue
            cell = ref.split(':')[0]
            digits = ''.join(char for char in cell if char.isdigit())
            if digits:
                result[int(digits)] = url
    return result


def _profile_column_indices(headers: list[str]) -> tuple[dict[str, int], str | None]:
    indices: dict[str, int] = {}
    regulation_header: str | None = None
    for index, header in enumerate(headers):
        if not header:
            continue
        field = resolve_import_header(header)
        if field in ('school_code', 'school_name', 'postgraduate_rate', 'regulation_url'):
            indices[field] = index
            if field == 'regulation_url':
                regulation_header = header
    return indices, regulation_header


def normalize_expert_profile_row(raw: dict[str, Any]) -> dict[str, Any]:
    from school_profile_service import infer_regulation_year, normalize_postgraduate_rate

    row: dict[str, Any] = {}
    regulation_year = None
    for cn_key, value in raw.items():
        if cn_key is None or value in (None, ''):
            continue
        key = resolve_import_header(str(cn_key))
        if key not in ('school_code', 'school_name', 'postgraduate_rate', 'regulation_url'):
            continue
        if key == 'regulation_url':
            regulation_year = infer_regulation_year(str(cn_key))
        if isinstance(value, str):
            value = value.strip()
        if value:
            row[key] = value
    if row.get('regulation_url') and regulation_year:
        row['regulation_year'] = regulation_year
    if row.get('postgraduate_rate'):
        row['postgraduate_rate'] = normalize_postgraduate_rate(row['postgraduate_rate'])
    return row


def _merge_expert_profile_row(deduped: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    code = str(row.get('school_code') or '').strip()
    name = str(row.get('school_name') or '').strip()
    key = code or name
    if not key:
        return
    current = deduped.get(key)
    if not current:
        deduped[key] = row
        return
    merged = {**current}
    for field, value in row.items():
        if value not in (None, '') and (not merged.get(field) or field == 'regulation_url'):
            merged[field] = value
    deduped[key] = merged


def _process_expert_profile_row(
    deduped: dict[str, dict[str, Any]],
    row_values: tuple[Any, ...],
    headers: list[str],
    col_indices: dict[str, int],
    regulation_header: str | None,
    regulation_url: str | None,
) -> None:
    raw: dict[str, Any] = {}
    for field, index in col_indices.items():
        if field == 'regulation_url':
            continue
        if index < len(row_values) and row_values[index] not in (None, ''):
            raw[headers[index]] = row_values[index]
    if regulation_url and regulation_header:
        raw[regulation_header] = regulation_url
    elif 'regulation_url' in col_indices:
        index = col_indices['regulation_url']
        if index < len(row_values) and row_values[index] not in (None, ''):
            raw[regulation_header or headers[index]] = row_values[index]
    normalized = normalize_expert_profile_row(raw)
    if not normalized.get('school_name') and not normalized.get('school_code'):
        return
    _merge_expert_profile_row(deduped, normalized)


def parse_expert_school_profiles_only(content: bytes) -> list[dict[str, Any]]:
    """快速解析专家版物理/历史表，仅提取院校保研率与招生章程（流式读取，按院校去重）。"""
    sheet_path = _active_sheet_path(content)
    hyperlink_rows = _extract_hyperlinks_by_row(content, sheet_path)
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    deduped: dict[str, dict[str, Any]] = {}
    header_idx: int | None = None
    headers: list[str] = []
    col_indices: dict[str, int] = {}
    regulation_header: str | None = None
    buffer: list[tuple[Any, ...]] = []

    try:
        worksheet = workbook.active
        for excel_row_num, row_values in enumerate(worksheet.iter_rows(values_only=True), start=1):
            if header_idx is None:
                buffer.append(row_values)
                labels = [str(cell).strip() if cell is not None else '' for cell in row_values]
                if len(buffer) < 25 and '院校名称' not in labels:
                    continue
                header_idx = find_header_row_index(buffer)
                headers = [str(cell).strip() if cell is not None else '' for cell in buffer[header_idx]]
                col_indices, regulation_header = _profile_column_indices(headers)
                if 'school_name' not in col_indices:
                    if len(buffer) < 25:
                        continue
                    raise ValueError('未找到院校名称列，请确认是河南专家版物理/历史表')
                for data_row_num in range(header_idx + 2, len(buffer) + 1):
                    data_index = data_row_num - 1
                    _process_expert_profile_row(
                        deduped,
                        buffer[data_index],
                        headers,
                        col_indices,
                        regulation_header,
                        hyperlink_rows.get(data_row_num),
                    )
                continue

            if excel_row_num <= header_idx + 1:
                continue
            _process_expert_profile_row(
                deduped,
                row_values,
                headers,
                col_indices,
                regulation_header,
                hyperlink_rows.get(excel_row_num),
            )
    finally:
        workbook.close()

    return list(deduped.values())


def run_sync_expert_school_profiles(filename: str, content: bytes) -> dict[str, Any]:
    rows = parse_expert_school_profiles_only(content)
    if not rows:
        raise ValueError('未解析到院校保研率或招生章程数据，请检查文件列名')
    return sync_school_profiles_from_expert_rows(filename, rows)


def get_or_create_school(connection, row: dict[str, Any]) -> int:
    from school_profile_service import ensure_school_profile_columns, school_profile_updates

    ensure_school_profile_columns()
    profile = school_profile_updates(row)
    school = row_to_dict(connection.execute('SELECT school_id FROM schools WHERE school_code = ?', [row['school_code']]).fetchone())
    if school:
        set_parts = [
            'school_name = ?', 'province = ?', 'city = ?', 'school_type = ?', 'education_level = ?',
            'is_985 = ?', 'is_211 = ?', 'is_double_first_class = ?', 'is_public = ?',
        ]
        values = [
            row['school_name'], row.get('school_province'), row.get('city'), row.get('school_type'),
            row.get('education_level'), row.get('is_985'), row.get('is_211'), row.get('is_double_first_class'),
            row.get('is_public'),
        ]
        for field, value in profile.items():
            set_parts.append(f'{field} = ?')
            values.append(value)
        values.append(school['school_id'])
        connection.execute(
            f"UPDATE schools SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP WHERE school_id = ?",
            values,
        )
        return school['school_id']

    columns = [
        'school_code', 'school_name', 'province', 'city', 'school_type', 'education_level',
        'is_985', 'is_211', 'is_double_first_class', 'is_public',
    ]
    values = [
        row['school_code'], row['school_name'], row.get('school_province'), row.get('city'), row.get('school_type'),
        row.get('education_level'), row.get('is_985'), row.get('is_211'), row.get('is_double_first_class'), row.get('is_public'),
    ]
    for field in ('postgraduate_rate', 'regulation_url', 'regulation_year', 'website'):
        if profile.get(field) not in (None, ''):
            columns.append(field)
            values.append(profile[field])

    placeholders = ', '.join(['?'] * len(columns))
    cursor = connection.execute(
        f'INSERT INTO schools ({", ".join(columns)}) VALUES ({placeholders})',
        values,
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


def sync_school_profiles_from_expert_rows(filename: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """从专家版录取表（物理/历史.xlsx）按院校去重，仅同步保研率与招生章程链接。"""
    from school_profile_service import school_profile_updates

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get('school_code') or '').strip()
        name = str(row.get('school_name') or '').strip()
        key = code or name
        if not key:
            continue
        profile = school_profile_updates(row)
        if not profile:
            continue
        current = deduped.get(key)
        if not current:
            deduped[key] = {**row, **profile}
            continue
        merged = {**current}
        for field, value in profile.items():
            if value not in (None, '') and (not merged.get(field) or field == 'regulation_url'):
                merged[field] = value
        deduped[key] = merged

    success_count = 0
    errors: list[str] = []
    with get_connection() as connection:
        for index, row in enumerate(deduped.values(), start=1):
            try:
                import_school_profile_row(connection, row)
                success_count += 1
            except Exception as exc:
                errors.append(f'院校 {row.get("school_name") or row.get("school_code")}: {exc}')
        fail_count = len(errors)
        error_message = '\n'.join(errors[:20]) if errors else None
        log_id = insert_import_log(
            connection,
            'school_profiles_from_expert',
            filename,
            len(deduped),
            success_count,
            fail_count,
            error_message,
        )
        connection.commit()
    return {
        'log_id': log_id,
        'total_count': len(deduped),
        'success_count': success_count,
        'fail_count': len(errors),
        'errors': errors[:20],
        'schools_with_regulation': sum(1 for row in deduped.values() if row.get('regulation_url')),
        'schools_with_postgraduate_rate': sum(1 for row in deduped.values() if row.get('postgraduate_rate')),
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


ART_SPORTS_REQUIRED_HEADERS = ['省份', '类别', '批次层次', '院校名称', '专业名称', '公式编号']
ART_SPORTS_HEADER_MAP = {
    '省份': 'province',
    '类别': 'category',
    '批次层次': 'batch_level',
    '院校名称': 'school_name',
    '专业名称': 'major_name',
    '公式编号': 'formula_id',
    '最低综合分2025': 'min_composite_2025',
    '最低综合分2024': 'min_composite_2024',
    '最低综合分2023': 'min_composite_2023',
    '城市': 'city',
}


def validate_art_sports_headers(headers: list[str]) -> None:
    missing = [header for header in ART_SPORTS_REQUIRED_HEADERS if header not in headers]
    if missing:
        raise ValueError(f'缺少必填字段：{", ".join(missing)}')


def parse_art_sports_file(filename: str, content: bytes) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == '.csv':
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        validate_art_sports_headers([str(h).strip() for h in headers])
        return [normalize_art_sports_row(dict(row)) for row in reader]
    if suffix in ('.xlsx', '.xls'):
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        worksheet = workbook.active
        rows = list(worksheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(cell).strip() if cell is not None else '' for cell in rows[0]]
        validate_art_sports_headers(headers)
        result = []
        for raw in rows[1:]:
            if not any(raw):
                continue
            item = {headers[i]: raw[i] for i in range(len(headers)) if headers[i]}
            result.append(normalize_art_sports_row(item))
        return result
    raise ValueError('仅支持 .csv 或 .xlsx 文件')


def normalize_art_sports_row(raw: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for cn_key, value in raw.items():
        if cn_key is None:
            continue
        key = ART_SPORTS_HEADER_MAP.get(str(cn_key).strip())
        if not key:
            continue
        if isinstance(value, str):
            value = value.strip()
        row[key] = value
    row['province'] = str(row.get('province') or '河南').replace('省', '')
    row['category'] = str(row.get('category') or '').strip()
    row['batch_level'] = str(row.get('batch_level') or '').strip()
    row['school_name'] = str(row.get('school_name') or '').strip()
    row['major_name'] = str(row.get('major_name') or '').strip()
    row['formula_id'] = to_int(row.get('formula_id'), 5)
    for field in ('min_composite_2025', 'min_composite_2024', 'min_composite_2023'):
        if field in row and row[field] not in (None, ''):
            try:
                row[field] = float(str(row[field]).strip())
            except ValueError:
                row[field] = None
    row['city'] = str(row.get('city') or '').strip()
    return row


def import_school_profile_row(connection, row: dict[str, Any]) -> int:
    from school_profile_service import ensure_school_profile_columns, school_profile_updates

    ensure_school_profile_columns()
    school_code = str(row.get('school_code') or '').strip()
    school_name = str(row.get('school_name') or '').strip()
    if not school_code and not school_name:
        raise ValueError('缺少院校代码或院校名称')
    profile = school_profile_updates(row)
    existing = None
    if school_code:
        existing = row_to_dict(connection.execute(
            'SELECT school_id FROM schools WHERE school_code = ?', [school_code]
        ).fetchone())
    if not existing and school_name:
        existing = row_to_dict(connection.execute(
            'SELECT school_id FROM schools WHERE school_name = ? LIMIT 1', [school_name]
        ).fetchone())
    if existing:
        if profile:
            set_parts = [f'{field} = ?' for field in profile]
            connection.execute(
                f"UPDATE schools SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP WHERE school_id = ?",
                list(profile.values()) + [existing['school_id']],
            )
        return int(existing['school_id'])

    code = school_code or f'SP{abs(hash(school_name)) % 100000:05d}'
    columns = ['school_code', 'school_name']
    values = [code, school_name or code]
    for field, value in profile.items():
        columns.append(field)
        values.append(value)
    cursor = connection.execute(
        f'INSERT INTO schools ({", ".join(columns)}) VALUES ({", ".join(["?"] * len(columns))})',
        values,
    )
    return int(cursor.lastrowid)


def normalize_school_profile_row(raw: dict[str, Any]) -> dict[str, Any]:
    from school_profile_service import infer_regulation_year, normalize_postgraduate_rate

    row: dict[str, Any] = {}
    regulation_year = None
    for cn_key, value in raw.items():
        if cn_key is None:
            continue
        key = resolve_import_header(cn_key)
        if not key:
            continue
        if key == 'regulation_url':
            regulation_year = infer_regulation_year(cn_key)
        if isinstance(value, str):
            value = value.strip()
        row[key] = value
    if row.get('regulation_url') and regulation_year:
        row['regulation_year'] = regulation_year
    if row.get('postgraduate_rate'):
        row['postgraduate_rate'] = normalize_postgraduate_rate(row['postgraduate_rate'])
    return row


def parse_school_profile_file(filename: str, content: bytes) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix == '.csv':
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        headers = [str(h).strip() for h in (reader.fieldnames or [])]
        if '院校名称' not in headers:
            raise ValueError('缺少必填字段：院校名称')
        return [normalize_school_profile_row(dict(row)) for row in reader]
    if suffix == '.xlsx':
        workbook = load_workbook(io.BytesIO(content), read_only=False, data_only=False)
        worksheet = workbook.active
        matrix = list(worksheet.iter_rows(values_only=False))
        if not matrix:
            return []
        plain_rows = [tuple(cell.value for cell in row) for row in matrix]
        header_idx = find_header_row_index(plain_rows)
        header_cells = matrix[header_idx]
        headers = [str(cell.value).strip() if cell.value is not None else '' for cell in header_cells]
        if '院校名称' not in headers:
            raise ValueError('缺少必填字段：院校名称')
        result = []
        for row_cells in matrix[header_idx + 1:]:
            if not any(cell.value is not None and str(cell.value).strip() != '' for cell in row_cells):
                continue
            raw = {
                headers[index]: cell_import_value(row_cells[index], headers[index])
                for index in range(min(len(headers), len(row_cells)))
                if headers[index]
            }
            result.append(normalize_school_profile_row(raw))
        return result
    raise ValueError('仅支持 .xlsx 或 .csv 文件')


def import_school_profile_rows(filename: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    success_count = 0
    errors: list[str] = []
    with get_connection() as connection:
        for index, row in enumerate(rows, start=2):
            try:
                if not row.get('school_name') and not row.get('school_code'):
                    raise ValueError(f'第 {index} 行缺少院校名称或院校代码')
                import_school_profile_row(connection, row)
                success_count += 1
            except Exception as exc:
                errors.append(str(exc))
        fail_count = len(errors)
        error_message = '\n'.join(errors[:20]) if errors else None
        log_id = insert_import_log(connection, 'school_profiles', filename, len(rows), success_count, fail_count, error_message)
        connection.commit()
    return {
        'log_id': log_id,
        'total_count': len(rows),
        'success_count': success_count,
        'fail_count': fail_count,
        'errors': errors[:20],
    }


def import_art_sports_rows(filename: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    from henan_art_sports_service import ensure_art_sports_admissions_table

    ensure_art_sports_admissions_table()
    success_count = 0
    errors: list[str] = []
    with get_connection() as connection:
        for index, row in enumerate(rows, start=2):
            try:
                for field in ['province', 'category', 'batch_level', 'school_name', 'major_name', 'formula_id']:
                    if not row.get(field):
                        raise ValueError(f'第 {index} 行缺少字段：{field}')
                if row['category'] not in ('艺术类', '体育类'):
                    raise ValueError(f'第 {index} 行类别须为艺术类或体育类')
                if row['batch_level'] not in ('本科', '专科'):
                    raise ValueError(f'第 {index} 行批次层次须为本科或专科')
                connection.execute(
                    '''
                    INSERT INTO art_sports_admissions (
                      province, category, batch_level, school_name, major_name, formula_id,
                      min_composite_2025, min_composite_2024, min_composite_2023, city
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(province, category, batch_level, school_name, major_name, formula_id) DO UPDATE SET
                      min_composite_2025 = excluded.min_composite_2025,
                      min_composite_2024 = excluded.min_composite_2024,
                      min_composite_2023 = excluded.min_composite_2023,
                      city = excluded.city
                    ''',
                    [
                        row['province'], row['category'], row['batch_level'], row['school_name'], row['major_name'],
                        int(row['formula_id']),
                        row.get('min_composite_2025'), row.get('min_composite_2024'), row.get('min_composite_2023'),
                        row.get('city') or '',
                    ],
                )
                success_count += 1
            except Exception as exc:
                errors.append(str(exc))
        fail_count = len(errors)
        error_message = '\n'.join(errors[:20]) if errors else None
        log_id = insert_import_log(connection, 'art_sports_admissions', filename, len(rows), success_count, fail_count, error_message)
        connection.commit()
    return {
        'log_id': log_id,
        'total_count': len(rows),
        'success_count': success_count,
        'fail_count': fail_count,
        'errors': errors[:20],
    }
