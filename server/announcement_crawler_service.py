"""全国高校 2026 招生公告采集（河南优先）。"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from typing import Any, Callable

from announcement_sources_config import (
    ANNOUNCEMENT_TYPES,
    ANNOUNCEMENT_YEAR_DEFAULT,
    EXCLUDE_KEYWORDS,
    PROVINCIAL_ANNOUNCEMENT_SOURCES,
    RECRUIT_KEYWORDS,
    SCHOOL_RECRUIT_PATHS,
    STRONG_RECRUIT_TITLE_KEYWORDS,
    STRONG_RECRUIT_URL_HINTS,
    YEAR_KEYWORDS,
)
from db import get_connection, row_to_dict, rows_to_dicts

REQUEST_INTERVAL = 0.35
USER_AGENT = 'Mozilla/5.0 (compatible; ZhiyuanAnnouncementCrawler/1.0; +https://zntb.lhyun.net)'
MAX_HTML_BYTES = 2_500_000


def ensure_announcement_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS enrollment_announcements (
              announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_org TEXT NOT NULL,
              source_type TEXT NOT NULL DEFAULT 'university',
              school_id INTEGER,
              school_code TEXT,
              school_name TEXT,
              province TEXT,
              target_province TEXT,
              year INTEGER NOT NULL DEFAULT 2026,
              title TEXT NOT NULL,
              announcement_type TEXT NOT NULL DEFAULT '招生公告',
              url TEXT NOT NULL,
              url_hash TEXT NOT NULL,
              file_url TEXT,
              file_ext TEXT,
              published_at TEXT,
              matched_keywords TEXT,
              mentions_henan INTEGER NOT NULL DEFAULT 0,
              crawl_status TEXT NOT NULL DEFAULT 'discovered',
              review_status TEXT NOT NULL DEFAULT 'pending',
              parse_status TEXT NOT NULL DEFAULT 'pending',
              parse_message TEXT,
              parsed_plan_count INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(url_hash)
            )
            '''
        )
        columns = {row[1] for row in connection.execute('PRAGMA table_info(enrollment_announcements)').fetchall()}
        if 'parse_status' not in columns:
            connection.execute("ALTER TABLE enrollment_announcements ADD COLUMN parse_status TEXT NOT NULL DEFAULT 'pending'")
        if 'parse_message' not in columns:
            connection.execute('ALTER TABLE enrollment_announcements ADD COLUMN parse_message TEXT')
        if 'parsed_plan_count' not in columns:
            connection.execute('ALTER TABLE enrollment_announcements ADD COLUMN parsed_plan_count INTEGER NOT NULL DEFAULT 0')
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS announcement_crawl_logs (
              log_id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_name TEXT NOT NULL,
              province TEXT,
              year INTEGER NOT NULL,
              source_total INTEGER NOT NULL DEFAULT 0,
              source_processed INTEGER NOT NULL DEFAULT 0,
              discovered_count INTEGER NOT NULL DEFAULT 0,
              new_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'running',
              error_message TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            )
            '''
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_announcements_province_year ON enrollment_announcements(target_province, year, review_status)'
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_announcements_henan ON enrollment_announcements(mentions_henan, year)'
        )
        connection.commit()


def url_hash(url: str) -> str:
    normalized = urllib.parse.urldefrag((url or '').strip())[0]
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def clean_text(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text or '')
    text = unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def detect_encoding(content_type: str | None) -> str:
    if content_type:
        match = re.search(r'charset=([^;]+)', content_type, re.I)
        if match:
            return match.group(1).strip()
    return 'utf-8'


def fetch_html(url: str, timeout: int = 15) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_HTML_BYTES)
        content_type = response.headers.get('Content-Type', '')
    encoding = detect_encoding(content_type)
    try:
        html = raw.decode(encoding, errors='replace')
    except LookupError:
        html = raw.decode('utf-8', errors='replace')
    return html, content_type


def extract_date_near(text: str) -> str:
    patterns = [
        r'(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})',
        r'(20\d{2}年\d{1,2}月\d{1,2}日)',
        r'(20\d{2}-\d{2}-\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ''


def classify_announcement_type(title: str, url: str) -> str:
    text = f'{title} {url}'
    if '章程' in text:
        return '招生章程'
    if '简章' in text:
        return '招生简章'
    if '计划' in text:
        return '招生计划'
    if '公告' in text or '通知' in text:
        return '招生公告'
    if '录取' in text or '分数' in text:
        return '录取信息'
    return '其他招生信息'


def is_excluded_announcement(title: str, url: str) -> bool:
    text = f'{title} {url}'
    return any(keyword in text for keyword in EXCLUDE_KEYWORDS)


def has_strong_recruit_signal(title: str, url: str) -> bool:
    if any(keyword in title for keyword in STRONG_RECRUIT_TITLE_KEYWORDS):
        return True
    url_lower = (url or '').lower()
    return any(hint in url_lower for hint in STRONG_RECRUIT_URL_HINTS)


def is_relevant_announcement(title: str, url: str, year: int = ANNOUNCEMENT_YEAR_DEFAULT) -> tuple[bool, list[str]]:
    if is_excluded_announcement(title, url):
        return False, []
    if not has_strong_recruit_signal(title, url):
        return False, []

    matched: list[str] = []
    for keyword in RECRUIT_KEYWORDS:
        if keyword in title or keyword in url:
            matched.append(keyword)
    if not matched:
        return False, matched

    year_text = str(year)
    has_year = year_text in title or year_text in url or any(key in title or key in url for key in YEAR_KEYWORDS)
    if not has_year and not any(key in title for key in ('章程', '简章', '计划', '招生公告', '招生简章', '招生计划')):
        return False, matched
    if has_year:
        matched.append(year_text)
    return True, matched


def should_auto_reject_announcement(title: str, url: str, announcement_type: str = '') -> bool:
    if is_excluded_announcement(title, url):
        return True
    if not has_strong_recruit_signal(title, url):
        return True
    if announcement_type == '其他招生信息':
        return True
    return False


def mentions_henan(title: str, url: str, context: str = '') -> bool:
    blob = f'{title} {url} {context}'
    return '河南' in blob or 'haeea' in blob.lower()


def discover_announcement_links(base_url: str, html: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for href, label in pattern.findall(html):
        if href.startswith(('javascript:', '#', 'mailto:', 'tel:')):
            continue
        absolute_url = urllib.parse.urljoin(base_url, href)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        title = clean_text(label) or absolute_url.rsplit('/', 1)[-1]
        if len(title) < 4:
            continue
        context = clean_text(label)
        published_at = extract_date_near(context)
        path = urllib.parse.urlparse(absolute_url).path.lower()
        file_ext = ''
        for ext in ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip'):
            if path.endswith(ext):
                file_ext = ext.lstrip('.')
                break
        records.append({
            'title': title[:500],
            'url': absolute_url,
            'file_ext': file_ext,
            'published_at': published_at,
            'context': context[:300],
        })
    return records


def upsert_announcement(data: dict[str, Any]) -> bool:
    ensure_announcement_tables()
    digest = url_hash(data['url'])
    with get_connection() as connection:
        existing = connection.execute(
            'SELECT announcement_id FROM enrollment_announcements WHERE url_hash = ?',
            [digest],
        ).fetchone()
        if existing:
            connection.execute(
                '''
                UPDATE enrollment_announcements
                SET title = ?, announcement_type = ?, matched_keywords = ?,
                    mentions_henan = ?, updated_at = CURRENT_TIMESTAMP
                WHERE url_hash = ?
                ''',
                [
                    data['title'],
                    data.get('announcement_type') or '招生公告',
                    ','.join(data.get('matched_keywords') or []),
                    1 if data.get('mentions_henan') else 0,
                    digest,
                ],
            )
            connection.commit()
            return False
        connection.execute(
            '''
            INSERT INTO enrollment_announcements (
              source_org, source_type, school_id, school_code, school_name, province, target_province,
              year, title, announcement_type, url, url_hash, file_url, file_ext, published_at,
              matched_keywords, mentions_henan, crawl_status, review_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                data['source_org'],
                data.get('source_type') or 'university',
                data.get('school_id'),
                data.get('school_code'),
                data.get('school_name'),
                data.get('province'),
                data.get('target_province'),
                int(data.get('year') or ANNOUNCEMENT_YEAR_DEFAULT),
                data['title'],
                data.get('announcement_type') or '招生公告',
                data['url'],
                digest,
                data.get('file_url') or (data['url'] if data.get('file_ext') else None),
                data.get('file_ext'),
                data.get('published_at'),
                ','.join(data.get('matched_keywords') or []),
                1 if data.get('mentions_henan') else 0,
                data.get('crawl_status') or 'discovered',
                data.get('review_status') or 'pending',
            ],
        )
        connection.commit()
        return True


def start_announcement_log(job_name: str, province: str, year: int, source_total: int) -> int:
    ensure_announcement_tables()
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO announcement_crawl_logs (job_name, province, year, source_total, status)
            VALUES (?, ?, ?, ?, 'running')
            ''',
            [job_name, province, year, source_total],
        )
        connection.commit()
        return int(cursor.lastrowid)


def finish_announcement_log(
    log_id: int,
    *,
    source_processed: int,
    discovered_count: int,
    new_count: int,
    status: str,
    error_message: str | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE announcement_crawl_logs
            SET source_processed = ?, discovered_count = ?, new_count = ?,
                status = ?, error_message = ?, finished_at = CURRENT_TIMESTAMP
            WHERE log_id = ?
            ''',
            [source_processed, discovered_count, new_count, status, error_message, log_id],
        )
        connection.commit()


def has_running_announcement_job() -> bool:
    ensure_announcement_tables()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT log_id FROM announcement_crawl_logs WHERE status = 'running' ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
    return bool(row)


def crawl_page_for_announcements(
    page_url: str,
    *,
    source_org: str,
    source_type: str,
    province: str = '',
    target_province: str = '',
    school_id: int | None = None,
    school_code: str | None = None,
    school_name: str | None = None,
    year: int = ANNOUNCEMENT_YEAR_DEFAULT,
) -> tuple[int, int]:
    html, _ = fetch_html(page_url)
    links = discover_announcement_links(page_url, html)
    discovered = 0
    created = 0
    for item in links:
        ok, keywords = is_relevant_announcement(item['title'], item['url'], year)
        if not ok:
            continue
        discovered += 1
        payload = {
            'source_org': source_org,
            'source_type': source_type,
            'school_id': school_id,
            'school_code': school_code,
            'school_name': school_name,
            'province': province,
            'target_province': target_province or province,
            'year': year,
            'title': item['title'],
            'announcement_type': classify_announcement_type(item['title'], item['url']),
            'url': item['url'],
            'file_ext': item.get('file_ext'),
            'published_at': item.get('published_at'),
            'matched_keywords': keywords,
            'mentions_henan': mentions_henan(item['title'], item['url'], item.get('context', '')),
            'review_status': 'pending',
        }
        if upsert_announcement(payload):
            created += 1
        time.sleep(0.02)
    return discovered, created


def crawl_provincial_sources(
    year: int = ANNOUNCEMENT_YEAR_DEFAULT,
    provinces: list[str] | None = None,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    selected = PROVINCIAL_ANNOUNCEMENT_SOURCES
    if provinces:
        province_set = set(provinces)
        selected = [item for item in selected if item.get('province') in province_set or not item.get('province')]
    urls: list[tuple[dict[str, Any], str]] = []
    for source in selected:
        for page_url in source.get('urls') or []:
            urls.append((source, page_url))

    log_id = start_announcement_log('provincial_sources', '、'.join(provinces or ['全国']), year, len(urls))
    discovered_total = 0
    new_total = 0
    errors: list[str] = []
    processed = 0
    try:
        for source, page_url in urls:
            if on_progress:
                on_progress(processed, len(urls), source.get('source_org'), page_url)
            try:
                found, created = crawl_page_for_announcements(
                    page_url,
                    source_org=source['source_org'],
                    source_type=source['source_type'],
                    province=source.get('province') or '',
                    target_province=source.get('province') or '',
                    year=year,
                )
                discovered_total += found
                new_total += created
            except Exception as exc:
                errors.append(f'{source.get("source_org")} {page_url}: {exc}')
            processed += 1
            time.sleep(REQUEST_INTERVAL)
        status = 'success' if not errors else 'partial'
        finish_announcement_log(
            log_id,
            source_processed=processed,
            discovered_count=discovered_total,
            new_count=new_total,
            status=status,
            error_message='\n'.join(errors[:30]) or None,
        )
        return {
            'log_id': log_id,
            'discovered_count': discovered_total,
            'new_count': new_total,
            'errors': errors[:20],
            'status': status,
        }
    except Exception as exc:
        finish_announcement_log(
            log_id,
            source_processed=processed,
            discovered_count=discovered_total,
            new_count=new_total,
            status='failed',
            error_message=str(exc),
        )
        raise


def list_schools_for_announcement_crawl(
    *,
    province: str = '',
    henan_priority: bool = True,
    school_limit: int | None = None,
) -> list[dict[str, Any]]:
    sql = '''
    SELECT school_id, school_code, school_name, province, city, website
    FROM schools
    WHERE website IS NOT NULL AND TRIM(website) != ''
    '''
    params: list[Any] = []
    if province:
        sql += ' AND province = ?'
        params.append(province)
    if henan_priority and not province:
        sql += ' ORDER BY CASE WHEN province = ? THEN 0 ELSE 1 END, school_id ASC'
        params.append('河南')
    else:
        sql += ' ORDER BY school_id ASC'
    if school_limit:
        sql += f' LIMIT {int(school_limit)}'
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def normalize_school_website(website: str) -> str:
    value = (website or '').strip()
    if not value:
        return ''
    if not value.startswith(('http://', 'https://')):
        value = f'https://{value}'
    return value.rstrip('/') + '/'


def crawl_university_websites(
    *,
    year: int = ANNOUNCEMENT_YEAR_DEFAULT,
    province: str = '',
    school_limit: int | None = None,
    henan_priority: bool = True,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    schools = list_schools_for_announcement_crawl(
        province=province,
        henan_priority=henan_priority,
        school_limit=school_limit,
    )
    log_id = start_announcement_log(
        'university_websites',
        province or ('河南优先' if henan_priority else '全国'),
        year,
        len(schools),
    )
    discovered_total = 0
    new_total = 0
    errors: list[str] = []
    processed = 0
    try:
        for school in schools:
            website = normalize_school_website(school.get('website') or '')
            if not website:
                processed += 1
                continue
            if on_progress:
                on_progress(processed, len(schools), school.get('school_name'), website)
            candidate_urls = [website]
            parsed = urllib.parse.urlparse(website)
            base = f'{parsed.scheme}://{parsed.netloc}'
            candidate_urls.extend(urllib.parse.urljoin(base + '/', path.lstrip('/')) for path in SCHOOL_RECRUIT_PATHS)
            school_found = 0
            school_created = 0
            for page_url in candidate_urls:
                try:
                    found, created = crawl_page_for_announcements(
                        page_url,
                        source_org=school.get('school_name') or '高校官网',
                        source_type='university',
                        province=school.get('province') or '',
                        target_province=province or '河南',
                        school_id=school.get('school_id'),
                        school_code=school.get('school_code'),
                        school_name=school.get('school_name'),
                        year=year,
                    )
                    school_found += found
                    school_created += created
                except Exception:
                    continue
                time.sleep(REQUEST_INTERVAL)
            discovered_total += school_found
            new_total += school_created
            if school_found == 0:
                errors.append(f'{school.get("school_name")}: 未发现 {year} 招生链接')
            processed += 1
        status = 'success' if processed else 'failed'
        if errors and processed:
            status = 'partial'
        finish_announcement_log(
            log_id,
            source_processed=processed,
            discovered_count=discovered_total,
            new_count=new_total,
            status=status,
            error_message='\n'.join(errors[:40]) or None,
        )
        return {
            'log_id': log_id,
            'school_total': len(schools),
            'school_processed': processed,
            'discovered_count': discovered_total,
            'new_count': new_total,
            'errors': errors[:20],
            'status': status,
        }
    except Exception as exc:
        finish_announcement_log(
            log_id,
            source_processed=processed,
            discovered_count=discovered_total,
            new_count=new_total,
            status='failed',
            error_message=str(exc),
        )
        raise


def run_announcement_job(
    *,
    year: int = ANNOUNCEMENT_YEAR_DEFAULT,
    province: str = '河南',
    school_limit: int | None = 200,
    include_provincial: bool = True,
    include_universities: bool = True,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """河南优先的 2026 招生公告采集任务。"""
    if has_running_announcement_job():
        raise RuntimeError('已有招生公告采集任务在运行')
    summary: dict[str, Any] = {'year': year, 'province': province, 'parts': []}
    if include_provincial:
        provinces = [province] if province else None
        summary['parts'].append(crawl_provincial_sources(year=year, provinces=provinces, on_progress=on_progress))
    if include_universities:
        summary['parts'].append(
            crawl_university_websites(
                year=year,
                province='',
                school_limit=school_limit,
                henan_priority=(province == '河南'),
                on_progress=on_progress,
            )
        )
    summary['discovered_count'] = sum(int(part.get('discovered_count') or 0) for part in summary['parts'])
    summary['new_count'] = sum(int(part.get('new_count') or 0) for part in summary['parts'])
    return summary


def search_announcements(
    *,
    keyword: str = '',
    province: str = '',
    school_name: str = '',
    year: int | None = None,
    henan_only: bool = False,
    review_status: str = '',
    announcement_type: str = '',
    limit: int = 200,
) -> list[dict[str, Any]]:
    ensure_announcement_tables()
    sql = 'SELECT * FROM enrollment_announcements WHERE 1=1'
    params: list[Any] = []
    if keyword:
        sql += ' AND (title LIKE ? OR school_name LIKE ? OR source_org LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like])
    if province:
        sql += ' AND (target_province = ? OR province = ? OR mentions_henan = 1)'
        params.extend([province, province])
    if year:
        sql += ' AND year = ?'
        params.append(year)
    if school_name:
        sql += ' AND (school_name LIKE ? OR title LIKE ? OR source_org LIKE ?)'
        like = f'%{school_name}%'
        params.extend([like, like, like])
    if henan_only:
        sql += ' AND mentions_henan = 1'
    if review_status:
        sql += ' AND review_status = ?'
        params.append(review_status)
    if announcement_type:
        sql += ' AND announcement_type = ?'
        params.append(announcement_type)
    sql += ' ORDER BY mentions_henan DESC, announcement_id DESC LIMIT ?'
    params.append(int(limit))
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def get_announcement(announcement_id: int) -> dict[str, Any] | None:
    ensure_announcement_tables()
    with get_connection() as connection:
        return row_to_dict(
            connection.execute(
                'SELECT * FROM enrollment_announcements WHERE announcement_id = ?',
                [announcement_id],
            ).fetchone()
        )


def get_announcement_stats() -> dict[str, Any]:
    ensure_announcement_tables()
    with get_connection() as connection:
        total = connection.execute('SELECT COUNT(*) FROM enrollment_announcements').fetchone()[0]
        henan = connection.execute(
            'SELECT COUNT(*) FROM enrollment_announcements WHERE mentions_henan = 1'
        ).fetchone()[0]
        pending = connection.execute(
            "SELECT COUNT(*) FROM enrollment_announcements WHERE review_status = 'pending'"
        ).fetchone()[0]
        y2026 = connection.execute(
            'SELECT COUNT(*) FROM enrollment_announcements WHERE year = 2026'
        ).fetchone()[0]
        schools_with_site = connection.execute(
            "SELECT COUNT(*) FROM schools WHERE website IS NOT NULL AND TRIM(website) != ''"
        ).fetchone()[0]
    return {
        'total': total,
        'henan_related': henan,
        'pending_review': pending,
        'year_2026': y2026,
        'schools_with_website': schools_with_site,
    }


def list_announcement_logs(limit: int = 30) -> list[dict[str, Any]]:
    ensure_announcement_tables()
    with get_connection() as connection:
        return rows_to_dicts(
            connection.execute(
                'SELECT * FROM announcement_crawl_logs ORDER BY log_id DESC LIMIT ?',
                [int(limit)],
            ).fetchall()
        )


def review_announcement(announcement_id: int, review_status: str) -> None:
    if review_status not in ('approved', 'rejected', 'pending'):
        raise ValueError('无效的审核状态')
    ensure_announcement_tables()
    with get_connection() as connection:
        connection.execute(
            'UPDATE enrollment_announcements SET review_status = ?, updated_at = CURRENT_TIMESTAMP WHERE announcement_id = ?',
            [review_status, announcement_id],
        )
        connection.commit()


def delete_announcement(announcement_id: int) -> bool:
    ensure_announcement_tables()
    with get_connection() as connection:
        cursor = connection.execute(
            'DELETE FROM enrollment_announcements WHERE announcement_id = ?',
            [int(announcement_id)],
        )
        connection.commit()
        return int(cursor.rowcount or 0) > 0


def is_protected_announcement(row: dict[str, Any]) -> bool:
    return (row.get('announcement_type') or '') == '招生官网' or (row.get('crawl_status') or '') == 'portal_link'


def auto_audit_announcements(*, province: str = '', limit: int = 5000) -> dict[str, int]:
    """自动审核：保留真实招生公告，驳回或删除无关内容。"""
    ensure_announcement_tables()
    rows = search_announcements(province=province, limit=limit)
    approved = 0
    rejected = 0
    skipped = 0
    for row in rows:
        if is_protected_announcement(row):
            skipped += 1
            continue
        title = str(row.get('title') or '')
        url = str(row.get('url') or '')
        announcement_type = str(row.get('announcement_type') or '')
        if should_auto_reject_announcement(title, url, announcement_type):
            review_announcement(int(row['announcement_id']), 'rejected')
            rejected += 1
        elif is_relevant_announcement(title, url, int(row.get('year') or ANNOUNCEMENT_YEAR_DEFAULT))[0]:
            review_announcement(int(row['announcement_id']), 'approved')
            approved += 1
        else:
            review_announcement(int(row['announcement_id']), 'rejected')
            rejected += 1
    return {'approved': approved, 'rejected': rejected, 'skipped': skipped, 'scanned': len(rows)}


def purge_irrelevant_announcements(*, province: str = '', limit: int = 5000) -> dict[str, int]:
    """直接删除非招生公告（保留招生官网链接）。"""
    ensure_announcement_tables()
    rows = search_announcements(province=province, limit=limit)
    deleted = 0
    skipped = 0
    for row in rows:
        if is_protected_announcement(row):
            skipped += 1
            continue
        title = str(row.get('title') or '')
        url = str(row.get('url') or '')
        announcement_type = str(row.get('announcement_type') or '')
        if should_auto_reject_announcement(title, url, announcement_type) or not is_relevant_announcement(
            title, url, int(row.get('year') or ANNOUNCEMENT_YEAR_DEFAULT)
        )[0]:
            if delete_announcement(int(row['announcement_id'])):
                deleted += 1
    return {'deleted': deleted, 'skipped': skipped, 'scanned': len(rows)}


def build_school_recruit_portal_url(website: str) -> str:
    website = normalize_school_website(website)
    parsed = urllib.parse.urlparse(website)
    base = f'{parsed.scheme}://{parsed.netloc}'
    return urllib.parse.urljoin(base + '/', 'zsb/')


def school_has_portal_link(school_id: int, year: int = ANNOUNCEMENT_YEAR_DEFAULT) -> bool:
    ensure_announcement_tables()
    with get_connection() as connection:
        row = connection.execute(
            '''
            SELECT announcement_id FROM enrollment_announcements
            WHERE school_id = ? AND year = ? AND announcement_type = '招生官网'
            LIMIT 1
            ''',
            [int(school_id), int(year)],
        ).fetchone()
        return bool(row)


def seed_school_recruit_portal_links(
    *,
    province: str = '河南',
    year: int = ANNOUNCEMENT_YEAR_DEFAULT,
    school_limit: int | None = None,
    only_missing: bool = True,
) -> dict[str, Any]:
    """为每所院校生成一条「招生官网」外链，小程序点击后 webview 跳转。"""
    schools = list_schools_for_announcement_crawl(
        province=province,
        henan_priority=False,
        school_limit=school_limit,
    )
    created = 0
    updated = 0
    skipped = 0
    for school in schools:
        school_id = school.get('school_id')
        website = normalize_school_website(school.get('website') or '')
        if not school_id or not website:
            skipped += 1
            continue
        if only_missing and school_has_portal_link(int(school_id), year):
            skipped += 1
            continue
        portal_url = build_school_recruit_portal_url(website)
        payload = {
            'source_org': school.get('school_name') or '高校官网',
            'source_type': 'university_portal',
            'school_id': school_id,
            'school_code': school.get('school_code'),
            'school_name': school.get('school_name'),
            'province': school.get('province') or '',
            'target_province': province or '河南',
            'year': year,
            'title': f'{school.get("school_name")} 招生信息网',
            'announcement_type': '招生官网',
            'url': portal_url,
            'matched_keywords': ['招生', '官网'],
            'mentions_henan': 1 if (school.get('province') or '') == '河南' else 0,
            'crawl_status': 'portal_link',
            'review_status': 'approved',
        }
        if upsert_announcement(payload):
            created += 1
        else:
            with get_connection() as connection:
                connection.execute(
                    '''
                    UPDATE enrollment_announcements
                    SET review_status = 'approved',
                        title = ?,
                        school_name = ?,
                        school_id = ?,
                        announcement_type = '招生官网',
                        crawl_status = 'portal_link',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE url_hash = ?
                    ''',
                    [
                        payload['title'],
                        payload['school_name'],
                        school_id,
                        url_hash(portal_url),
                    ],
                )
                connection.commit()
            updated += 1
    return {
        'school_total': len(schools),
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'province': province,
        'year': year,
    }


def create_manual_announcement(
    *,
    title: str,
    url: str,
    source_org: str = '',
    school_name: str = '',
    school_id: int | None = None,
    province: str = '河南',
    year: int = ANNOUNCEMENT_YEAR_DEFAULT,
    announcement_type: str = '招生公告',
    review_status: str = 'approved',
) -> bool:
    title = (title or '').strip()
    url = (url or '').strip()
    if not title or not url:
        raise ValueError('标题和链接不能为空')
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    return upsert_announcement({
        'source_org': source_org or school_name or '手动添加',
        'source_type': 'manual',
        'school_id': school_id,
        'school_name': school_name or None,
        'province': province,
        'target_province': province,
        'year': year,
        'title': title,
        'announcement_type': announcement_type,
        'url': url,
        'matched_keywords': ['招生'],
        'mentions_henan': 1 if province == '河南' else 0,
        'crawl_status': 'manual',
        'review_status': review_status,
    })


def bulk_review_announcements(
    review_status: str,
    *,
    from_status: str = 'pending',
    announcement_type: str = '',
    province: str = '',
) -> int:
    if review_status not in ('approved', 'rejected', 'pending'):
        raise ValueError('无效的审核状态')
    ensure_announcement_tables()
    sql = 'UPDATE enrollment_announcements SET review_status = ?, updated_at = CURRENT_TIMESTAMP WHERE review_status = ?'
    params: list[Any] = [review_status, from_status]
    if announcement_type:
        sql += ' AND announcement_type = ?'
        params.append(announcement_type)
    if province:
        sql += ' AND (target_province = ? OR province = ? OR mentions_henan = 1)'
        params.extend([province, province])
    with get_connection() as connection:
        cursor = connection.execute(sql, params)
        connection.commit()
        return int(cursor.rowcount or 0)


if __name__ == '__main__':
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description='采集全国高校 2026 招生公告（河南优先）')
    parser.add_argument('--year', type=int, default=ANNOUNCEMENT_YEAR_DEFAULT)
    parser.add_argument('--province', default='河南', help='优先省份，传空字符串表示不限')
    parser.add_argument('--school-limit', type=int, default=200, help='高校官网扫描数量，0=不限制')
    parser.add_argument('--provincial-only', action='store_true')
    parser.add_argument('--universities-only', action='store_true')
    args = parser.parse_args()
    limit = None if args.school_limit == 0 else args.school_limit
    try:
        result = run_announcement_job(
            year=args.year,
            province=args.province,
            school_limit=limit,
            include_provincial=not args.universities_only,
            include_universities=not args.provincial_only,
            on_progress=lambda done, total, name, url: print(f'[{done + 1}/{total}] {name} {url}', flush=True),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    except KeyboardInterrupt:
        sys.exit(130)
