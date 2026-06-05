import re
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts

ATTACHMENT_EXTENSIONS = ('.pdf', '.xls', '.xlsx', '.csv', '.doc', '.docx', '.zip')
KEYWORDS = ('招生', '计划', '章程', '录取', '分数', '专业', '选科', '简章')


def ensure_fetch_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS data_sources (
              source_id INTEGER PRIMARY KEY AUTOINCREMENT,
              school_id INTEGER,
              school_code TEXT,
              school_name TEXT NOT NULL,
              source_name TEXT NOT NULL,
              source_type TEXT NOT NULL DEFAULT '高校官网',
              data_type TEXT NOT NULL DEFAULT '招生信息',
              year INTEGER,
              province TEXT,
              url TEXT NOT NULL,
              parser_type TEXT NOT NULL DEFAULT 'link_discovery',
              is_active INTEGER NOT NULL DEFAULT 1,
              last_fetch_at TEXT,
              last_status TEXT,
              remark TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS data_fetch_tasks (
              task_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id INTEGER NOT NULL,
              task_status TEXT NOT NULL DEFAULT 'pending',
              fetch_url TEXT NOT NULL,
              content_type TEXT,
              page_title TEXT,
              links_count INTEGER NOT NULL DEFAULT 0,
              matched_count INTEGER NOT NULL DEFAULT 0,
              error_message TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS data_fetch_records (
              record_id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id INTEGER NOT NULL,
              source_id INTEGER NOT NULL,
              record_type TEXT NOT NULL,
              title TEXT,
              url TEXT NOT NULL,
              file_ext TEXT,
              matched_keyword TEXT,
              review_status TEXT NOT NULL DEFAULT 'pending',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (task_id) REFERENCES data_fetch_tasks(task_id) ON DELETE CASCADE,
              FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS admission_brochures (
              brochure_id INTEGER PRIMARY KEY AUTOINCREMENT,
              school_id INTEGER,
              school_code TEXT,
              school_name TEXT NOT NULL,
              year INTEGER,
              title TEXT NOT NULL,
              source_url TEXT NOT NULL,
              file_url TEXT,
              content_text TEXT,
              admission_rule TEXT,
              adjustment_rule TEXT,
              single_subject_requirement TEXT,
              physical_requirement TEXT,
              language_requirement TEXT,
              tuition_rule TEXT,
              published_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        connection.commit()


def create_source(data: dict[str, Any]) -> int:
    ensure_fetch_tables()
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO data_sources (
              school_code, school_name, source_name, source_type, data_type, year, province, url,
              parser_type, is_active, remark
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                data.get('school_code'), data['school_name'], data.get('source_name') or data['school_name'],
                data.get('source_type') or '高校官网', data.get('data_type') or '招生信息',
                data.get('year') or None, data.get('province'), data['url'],
                data.get('parser_type') or 'link_discovery', 1, data.get('remark')
            ]
        )
        connection.commit()
        return cursor.lastrowid


def list_sources(keyword: str = '') -> list[dict[str, Any]]:
    ensure_fetch_tables()
    sql = 'SELECT * FROM data_sources WHERE 1=1'
    params: list[Any] = []
    if keyword:
        sql += ' AND (school_name LIKE ? OR source_name LIKE ? OR url LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like])
    sql += ' ORDER BY source_id DESC LIMIT 100'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def list_tasks(source_id: int | None = None) -> list[dict[str, Any]]:
    ensure_fetch_tables()
    sql = '''
    SELECT t.*, s.school_name, s.source_name
    FROM data_fetch_tasks t
    JOIN data_sources s ON s.source_id = t.source_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if source_id:
        sql += ' AND t.source_id = ?'
        params.append(source_id)
    sql += ' ORDER BY t.task_id DESC LIMIT 100'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def list_records(task_id: int | None = None, source_id: int | None = None, review_status: str = '') -> list[dict[str, Any]]:
    ensure_fetch_tables()
    sql = '''
    SELECT r.*, s.school_name, s.data_type
    FROM data_fetch_records r
    LEFT JOIN data_sources s ON s.source_id = r.source_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if task_id:
        sql += ' AND r.task_id = ?'
        params.append(task_id)
    if source_id:
        sql += ' AND r.source_id = ?'
        params.append(source_id)
    if review_status:
        sql += ' AND r.review_status = ?'
        params.append(review_status)
    sql += ' ORDER BY r.record_id DESC LIMIT 200'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def update_source(source_id: int, data: dict[str, Any]) -> None:
    ensure_fetch_tables()
    with get_connection() as connection:
        source = row_to_dict(connection.execute('SELECT source_id FROM data_sources WHERE source_id = ?', [source_id]).fetchone())
        if not source:
            raise ValueError('数据源不存在')
        connection.execute(
            '''UPDATE data_sources SET school_name=?, school_code=?, source_name=?, data_type=?,
               year=?, province=?, url=?, remark=?, is_active=?, updated_at=CURRENT_TIMESTAMP
               WHERE source_id=?''',
            [
                data['school_name'], data.get('school_code'), data.get('source_name') or data['school_name'],
                data.get('data_type') or '招生信息',
                int(data['year']) if data.get('year') and str(data['year']).isdigit() else None,
                data.get('province'), data['url'],
                data.get('remark'), 1 if data.get('is_active', True) else 0, source_id
            ]
        )
        connection.commit()


def delete_source(source_id: int) -> None:
    ensure_fetch_tables()
    with get_connection() as connection:
        connection.execute('DELETE FROM data_sources WHERE source_id = ?', [source_id])
        connection.commit()


def review_record(record_id: int, review_status: str) -> None:
    ensure_fetch_tables()
    if review_status not in ('approved', 'rejected', 'pending'):
        raise ValueError('无效的审核状态')
    with get_connection() as connection:
        connection.execute(
            'UPDATE data_fetch_records SET review_status = ? WHERE record_id = ?',
            [review_status, record_id]
        )
        connection.commit()


def archive_record_to_brochure(record_id: int) -> int:
    ensure_fetch_tables()
    with get_connection() as connection:
        record = row_to_dict(connection.execute(
            '''
            SELECT r.*, s.school_id, s.school_code, s.school_name, s.year, s.data_type
            FROM data_fetch_records r
            JOIN data_sources s ON s.source_id = r.source_id
            WHERE r.record_id = ?
            ''',
            [record_id]
        ).fetchone())
        if not record:
            raise ValueError('采集记录不存在')
        cursor = connection.execute(
            '''
            INSERT INTO admission_brochures (school_id, school_code, school_name, year, title, source_url, file_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                record.get('school_id'), record.get('school_code'), record.get('school_name'),
                record.get('year'), record.get('title') or '招生信息',
                record['url'], record['url'] if record.get('file_ext') else None
            ]
        )
        connection.execute(
            'UPDATE data_fetch_records SET review_status = ? WHERE record_id = ?',
            ['approved', record_id]
        )
        connection.commit()
        return cursor.lastrowid


def list_brochures(keyword: str = '') -> list[dict[str, Any]]:
    ensure_fetch_tables()
    sql = 'SELECT * FROM admission_brochures WHERE 1=1'
    params: list[Any] = []
    if keyword:
        sql += ' AND (school_name LIKE ? OR title LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like])
    sql += ' ORDER BY brochure_id DESC LIMIT 100'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def detect_encoding(content_type: str | None) -> str:
    if content_type:
        match = re.search(r'charset=([^;]+)', content_type, re.I)
        if match:
            return match.group(1).strip()
    return 'utf-8'


def extract_page_title(html: str) -> str:
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
    if not match:
        return ''
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', match.group(1)))).strip()


def clean_text(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def classify_link(title: str, url: str) -> tuple[str, str, str]:
    parsed_path = urllib.parse.urlparse(url).path.lower()
    ext = ''
    for item in ATTACHMENT_EXTENSIONS:
        if parsed_path.endswith(item):
            ext = item.lstrip('.')
            break
    matched_keyword = next((keyword for keyword in KEYWORDS if keyword in title or keyword in url), '')
    if ext:
        return 'attachment', ext, matched_keyword
    return 'page', '', matched_keyword


def discover_links(base_url: str, html: str) -> list[dict[str, str]]:
    records = []
    seen = set()
    pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for href, label in pattern.findall(html):
        if href.startswith(('javascript:', '#', 'mailto:')):
            continue
        absolute_url = urllib.parse.urljoin(base_url, href)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        title = clean_text(label) or absolute_url.rsplit('/', 1)[-1]
        record_type, ext, matched_keyword = classify_link(title, absolute_url)
        if record_type == 'attachment' or matched_keyword:
            records.append({
                'record_type': record_type,
                'title': title[:300],
                'url': absolute_url,
                'file_ext': ext,
                'matched_keyword': matched_keyword
            })
    return records


def fetch_source(source_id: int) -> dict[str, Any]:
    ensure_fetch_tables()
    with get_connection() as connection:
        source = row_to_dict(connection.execute('SELECT * FROM data_sources WHERE source_id = ?', [source_id]).fetchone())
        if not source:
            raise ValueError('数据源不存在')
        cursor = connection.execute(
            'INSERT INTO data_fetch_tasks (source_id, fetch_url, task_status) VALUES (?, ?, ?)',
            [source_id, source['url'], 'running']
        )
        task_id = cursor.lastrowid
        connection.commit()

    try:
        request = urllib.request.Request(
            source['url'],
            headers={'User-Agent': 'Mozilla/5.0 ZhiyuanDataFetcher/1.0'}
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(2_000_000)
            content_type = response.headers.get('Content-Type', '')
        encoding = detect_encoding(content_type)
        try:
            html = raw.decode(encoding, errors='replace')
        except LookupError:
            html = raw.decode('utf-8', errors='replace')
        title = extract_page_title(html)
        records = discover_links(source['url'], html)
        with get_connection() as connection:
            for record in records:
                connection.execute(
                    '''
                    INSERT INTO data_fetch_records (task_id, source_id, record_type, title, url, file_ext, matched_keyword)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    [task_id, source_id, record['record_type'], record['title'], record['url'], record['file_ext'], record['matched_keyword']]
                )
            connection.execute(
                '''
                UPDATE data_fetch_tasks SET task_status = ?, content_type = ?, page_title = ?, links_count = ?,
                  matched_count = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?
                ''',
                ['success', content_type, title, len(records), len(records), task_id]
            )
            connection.execute(
                'UPDATE data_sources SET last_fetch_at = CURRENT_TIMESTAMP, last_status = ?, updated_at = CURRENT_TIMESTAMP WHERE source_id = ?',
                ['success', source_id]
            )
            connection.commit()
        return {'task_id': task_id, 'status': 'success', 'matched_count': len(records), 'records': records}
    except Exception as exc:
        with get_connection() as connection:
            connection.execute(
                'UPDATE data_fetch_tasks SET task_status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?',
                ['failed', str(exc), task_id]
            )
            connection.execute(
                'UPDATE data_sources SET last_fetch_at = CURRENT_TIMESTAMP, last_status = ?, updated_at = CURRENT_TIMESTAMP WHERE source_id = ?',
                ['failed', source_id]
            )
            connection.commit()
        raise
