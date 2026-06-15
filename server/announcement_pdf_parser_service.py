"""河南等省份招生公告 PDF/XLSX 解析并写入 enrollment_plans。"""

from __future__ import annotations

import io
import re
import urllib.parse
import urllib.request
from typing import Any

from announcement_crawler_service import USER_AGENT, ensure_announcement_tables, get_announcement
from db import get_connection
from import_service import get_or_create_major, get_or_create_school, import_plan_rows, parse_import_file, upsert_plan

DEFAULT_PROVINCE = '河南'
DEFAULT_BATCH = '本科批'
DEFAULT_YEAR = 2026
PLAN_FILE_EXTENSIONS = ('pdf', 'xls', 'xlsx', 'csv')

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'year': ('年份', '年度'),
    'province': ('省份', '生源省份', '生源地'),
    'batch': ('批次', '录取批次', '报考批次'),
    'school_code': ('院校代号', '院校代码', '学校代号', '学校代码', '院校招生代码'),
    'school_name': ('院校名称', '学校名称', '招生院校'),
    'major_code': ('专业代号', '专业代码', '专业招生代码'),
    'major_name': ('专业名称', '专业', '专业全称'),
    'enrollment_count': ('计划数', '招生人数', '计划人数', '人数', '拟招生人数'),
    'subject_requirement': ('选科要求', '科目要求', '选考要求'),
    'tuition': ('学费', '收费标准'),
    'duration': ('学制', '年限'),
}


def _normalize_header(value: Any) -> str:
    return re.sub(r'\s+', '', str(value or '').strip())


def map_header_to_field(header: str) -> str | None:
    normalized = _normalize_header(header)
    if not normalized:
        return None
    for field, aliases in COLUMN_ALIASES.items():
        if normalized in aliases:
            return field
    return None


def download_announcement_file(url: str, timeout: int = 30) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read(15_000_000)
        path = urllib.parse.urlparse(url).path.lower()
    filename = path.rsplit('/', 1)[-1] if path else 'announcement.bin'
    return content, filename


def guess_file_ext(url: str, filename: str, content: bytes) -> str:
    for candidate in (filename, url):
        lower = (candidate or '').lower()
        for ext in PLAN_FILE_EXTENSIONS:
            if lower.endswith(f'.{ext}'):
                return ext
    if content[:4] == b'%PDF':
        return 'pdf'
    if content[:2] == b'PK':
        return 'xlsx'
    return ''


def table_rows_to_records(
    table: list[list[Any]],
    *,
    year: int = DEFAULT_YEAR,
    province: str = DEFAULT_PROVINCE,
    batch: str = DEFAULT_BATCH,
) -> list[dict[str, Any]]:
    if not table:
        return []
    header_row_index = -1
    field_indexes: dict[str, int] = {}
    for index, row in enumerate(table[:8]):
        mapping: dict[str, int] = {}
        for col_index, cell in enumerate(row or []):
            field = map_header_to_field(str(cell or ''))
            if field:
                mapping[field] = col_index
        if {'school_code', 'school_name', 'major_code', 'major_name'}.issubset(mapping.keys()):
            header_row_index = index
            field_indexes = mapping
            break
        if {'school_name', 'major_name'}.issubset(mapping.keys()) and len(mapping) >= 3:
            header_row_index = index
            field_indexes = mapping
            break
    if header_row_index < 0:
        return []

    records: list[dict[str, Any]] = []
    for row in table[header_row_index + 1:]:
        if not row or not any(str(cell or '').strip() for cell in row):
            continue

        def cell_value(field: str, default: Any = '') -> Any:
            idx = field_indexes.get(field)
            if idx is None or idx >= len(row):
                return default
            return row[idx]

        school_code = str(cell_value('school_code', '')).strip()
        school_name = str(cell_value('school_name', '')).strip()
        major_code = str(cell_value('major_code', '')).strip()
        major_name = str(cell_value('major_name', '')).strip()
        if not school_name or not major_name:
            continue
        if not school_code:
            school_code = school_name[:5]
        if not major_code:
            major_code = f'M{len(records) + 1:04d}'

        count_raw = cell_value('enrollment_count', None)
        enrollment_count = None
        if count_raw not in (None, ''):
            try:
                enrollment_count = int(float(str(count_raw).strip()))
            except ValueError:
                enrollment_count = None

        records.append({
            'year': year,
            'province': str(cell_value('province', province) or province).strip() or province,
            'batch': str(cell_value('batch', batch) or batch).strip() or batch,
            'school_code': school_code,
            'school_name': school_name,
            'major_code': major_code,
            'major_name': major_name,
            'enrollment_count': enrollment_count,
            'subject_requirement': str(cell_value('subject_requirement', '') or '').strip(),
            'tuition': cell_value('tuition', None),
            'duration': str(cell_value('duration', '') or '').strip(),
            'school_province': province,
            'city': '',
            'school_type': '',
            'education_level': '本科',
            'is_985': 0,
            'is_211': 0,
            'is_double_first_class': 0,
            'is_public': 1,
            'major_category': '',
            'major_type': '',
            'degree_type': '本科',
        })
    return records


def extract_records_from_pdf(
    content: bytes,
    *,
    year: int = DEFAULT_YEAR,
    province: str = DEFAULT_PROVINCE,
    batch: str = DEFAULT_BATCH,
) -> list[dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError('服务器未安装 pdfplumber，请执行 pip install pdfplumber') from exc

    records: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                records.extend(
                    table_rows_to_records(table, year=year, province=province, batch=batch)
                )
            if records:
                continue
            text = page.extract_text() or ''
            records.extend(_extract_records_from_text(text, year=year, province=province, batch=batch))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in records:
        key = (row['school_code'], row['major_code'], row['major_name'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _extract_records_from_text(
    text: str,
    *,
    year: int,
    province: str,
    batch: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    line_pattern = re.compile(
        r'(?P<school_code>\d{4})\s+(?P<school_name>[\u4e00-\u9fa5（）()·]+?)\s+'
        r'(?P<major_code>\d{2,3})\s+(?P<major_name>[\u4e00-\u9fa5（）()·、\-]+?)\s+'
        r'(?P<count>\d{1,4})'
    )
    for match in line_pattern.finditer(text):
        records.append({
            'year': year,
            'province': province,
            'batch': batch,
            'school_code': match.group('school_code'),
            'school_name': match.group('school_name').strip(),
            'major_code': match.group('major_code'),
            'major_name': match.group('major_name').strip(),
            'enrollment_count': int(match.group('count')),
            'school_province': province,
            'city': '',
            'school_type': '',
            'education_level': '本科',
            'is_985': 0,
            'is_211': 0,
            'is_double_first_class': 0,
            'is_public': 1,
            'major_category': '',
            'major_type': '',
            'degree_type': '本科',
            'subject_requirement': '',
            'duration': '',
        })
    return records


def extract_records_from_file(
    content: bytes,
    filename: str,
    *,
    year: int = DEFAULT_YEAR,
    province: str = DEFAULT_PROVINCE,
    batch: str = DEFAULT_BATCH,
) -> list[dict[str, Any]]:
    ext = guess_file_ext('', filename, content)
    if ext in ('xlsx', 'xls', 'csv'):
        rows = parse_import_file(filename if '.' in filename else f'file.{ext}', content)
        for row in rows:
            row.setdefault('year', year)
            row.setdefault('province', province)
            row.setdefault('batch', batch)
        return rows
    if ext == 'pdf':
        return extract_records_from_pdf(content, year=year, province=province, batch=batch)
    raise ValueError(f'不支持的文件类型：{filename or ext or "unknown"}')


def update_announcement_parse_result(
    announcement_id: int,
    *,
    parse_status: str,
    parse_message: str = '',
    parsed_plan_count: int = 0,
) -> None:
    ensure_announcement_tables()
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE enrollment_announcements
            SET parse_status = ?, parse_message = ?, parsed_plan_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE announcement_id = ?
            ''',
            [parse_status, parse_message[:2000], parsed_plan_count, announcement_id],
        )
        connection.commit()


def parse_announcement_plans(
    announcement_id: int,
    *,
    default_batch: str = DEFAULT_BATCH,
) -> dict[str, Any]:
    announcement = get_announcement(announcement_id)
    if not announcement:
        raise ValueError('公告不存在')
    file_url = announcement.get('file_url') or announcement.get('url')
    if not file_url:
        raise ValueError('公告缺少可下载链接')

    ext = (announcement.get('file_ext') or guess_file_ext(file_url, file_url, b'')).lower()
    if ext not in PLAN_FILE_EXTENSIONS and not file_url.lower().endswith('.pdf'):
        raise ValueError('仅支持 PDF / Excel / CSV 招生计划文件解析')

    content, filename = download_announcement_file(file_url)
    year = int(announcement.get('year') or DEFAULT_YEAR)
    province = announcement.get('target_province') or announcement.get('province') or DEFAULT_PROVINCE
    batch = default_batch
    if '专科' in (announcement.get('title') or ''):
        batch = '专科批'

    rows = extract_records_from_file(content, filename, year=year, province=province, batch=batch)
    if not rows:
        update_announcement_parse_result(
            announcement_id,
            parse_status='failed',
            parse_message='未能从文件中识别出招生计划表格，请检查版式或改用手动导入',
            parsed_plan_count=0,
        )
        return {
            'announcement_id': announcement_id,
            'parse_status': 'failed',
            'parsed_plan_count': 0,
            'import_result': None,
            'message': '未能识别表格',
        }

    import_result = import_plan_rows(
        f'announcement_{announcement_id}_{filename}',
        rows,
    )
    status = 'parsed' if import_result['success_count'] > 0 else 'failed'
    message = (
        f'成功导入 {import_result["success_count"]} 条计划'
        if import_result['success_count']
        else (import_result.get('errors') or ['导入失败'])[0]
    )
    update_announcement_parse_result(
        announcement_id,
        parse_status=status,
        parse_message=message,
        parsed_plan_count=import_result['success_count'],
    )
    return {
        'announcement_id': announcement_id,
        'parse_status': status,
        'parsed_plan_count': import_result['success_count'],
        'import_result': import_result,
        'message': message,
    }


def parse_pending_henan_announcements(limit: int = 20) -> list[dict[str, Any]]:
    ensure_announcement_tables()
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT announcement_id FROM enrollment_announcements
            WHERE (target_province = '河南' OR province = '河南' OR mentions_henan = 1)
              AND year >= 2026
              AND review_status = 'approved'
              AND (parse_status IS NULL OR parse_status IN ('pending', 'failed'))
              AND (
                LOWER(COALESCE(file_ext, '')) IN ('pdf', 'xls', 'xlsx', 'csv')
                OR LOWER(url) LIKE '%.pdf'
                OR LOWER(url) LIKE '%.xlsx'
                OR LOWER(url) LIKE '%.xls'
              )
            ORDER BY announcement_id DESC
            LIMIT ?
            ''',
            [int(limit)],
        ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            results.append(parse_announcement_plans(int(row['announcement_id'])))
        except Exception as exc:
            update_announcement_parse_result(
                int(row['announcement_id']),
                parse_status='failed',
                parse_message=str(exc),
                parsed_plan_count=0,
            )
            results.append({
                'announcement_id': int(row['announcement_id']),
                'parse_status': 'failed',
                'message': str(exc),
            })
    return results
