"""一分一段表：PDF/Excel 解析、入库与分数位次互查。"""

from __future__ import annotations

import io
import re
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
SCORE_HEADER_ALIASES: tuple[str, ...] = ('分数', '文化课成绩', '高考成绩', '分值', '总分')
SEGMENT_COUNT_ALIASES: tuple[str, ...] = ('本段人数', '人数', '同分人数', '本段人數')
CUMULATIVE_ALIASES: tuple[str, ...] = ('累计人数', '累计', '累计位次', '位次', '累计人數')
BATCH_ALIASES: tuple[str, ...] = ('本科批', '专科批', '本科', '专科')


def _normalize_header(value: Any) -> str:
    return re.sub(r'\s+', '', str(value or '').strip())


def _match_alias(header: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalize_header(header)
    return any(alias in normalized or normalized in alias for alias in aliases)


def ensure_score_segment_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS score_rank_tables (
              table_id INTEGER PRIMARY KEY AUTOINCREMENT,
              province TEXT NOT NULL,
              year INTEGER NOT NULL,
              batch TEXT NOT NULL DEFAULT '',
              exam_type TEXT NOT NULL DEFAULT '普通类',
              subject_type TEXT NOT NULL DEFAULT '',
              title TEXT,
              source_file TEXT,
              row_count INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(province, year, batch, subject_type)
            )
            '''
        )
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS score_rank_segments (
              segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
              table_id INTEGER NOT NULL,
              score INTEGER NOT NULL,
              segment_count INTEGER,
              cumulative_rank INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(table_id, score),
              FOREIGN KEY (table_id) REFERENCES score_rank_tables(table_id) ON DELETE CASCADE
            )
            '''
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_score_rank_lookup ON score_rank_segments(table_id, score)'
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_score_rank_tables_query ON score_rank_tables(province, year, batch)'
        )
        connection.commit()


def _to_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(float(str(value).strip().replace(',', '')))
    except ValueError:
        return None


def parse_table_matrix(
    table: list[list[Any]],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    header_indexes: dict[str, int] = {}
    header_row_index = -1
    for index, row in enumerate(table[:10]):
        mapping: dict[str, int] = {}
        for col_index, cell in enumerate(row or []):
            header = str(cell or '').strip()
            if not header:
                continue
            if _match_alias(header, SCORE_HEADER_ALIASES):
                mapping['score'] = col_index
            elif _match_alias(header, SEGMENT_COUNT_ALIASES):
                mapping['segment_count'] = col_index
            elif _match_alias(header, CUMULATIVE_ALIASES):
                mapping['cumulative_rank'] = col_index
        if 'score' in mapping and ('cumulative_rank' in mapping or 'segment_count' in mapping):
            header_indexes = mapping
            header_row_index = index
            break
        if 'score' in mapping and len(mapping) >= 2:
            header_indexes = mapping
            header_row_index = index
            break

    if header_row_index < 0:
        return {}, []

    rows: list[dict[str, Any]] = []
    for row in table[header_row_index + 1:]:
        if not row:
            continue

        def value(key: str) -> Any:
            idx = header_indexes.get(key)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        score = _to_int(value('score'))
        if score is None or score < 0 or score > 900:
            continue
        segment_count = _to_int(value('segment_count'))
        cumulative_rank = _to_int(value('cumulative_rank'))
        rows.append({
            'score': score,
            'segment_count': segment_count,
            'cumulative_rank': cumulative_rank,
        })
    return header_indexes, rows


def finalize_segment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = [row for row in rows if row.get('score') is not None]
    if not cleaned:
        return []

    has_cumulative = any(row.get('cumulative_rank') for row in cleaned)
    if has_cumulative:
        result = []
        for row in cleaned:
            cumulative = row.get('cumulative_rank')
            if cumulative is None:
                continue
            result.append({
                'score': int(row['score']),
                'segment_count': row.get('segment_count'),
                'cumulative_rank': int(cumulative),
            })
        return sorted(result, key=lambda item: item['score'], reverse=True)

    sorted_rows = sorted(cleaned, key=lambda item: item['score'], reverse=True)
    cumulative = 0
    result: list[dict[str, Any]] = []
    for row in sorted_rows:
        count = int(row.get('segment_count') or 0)
        cumulative += max(count, 0)
        result.append({
            'score': int(row['score']),
            'segment_count': count or None,
            'cumulative_rank': cumulative,
        })
    return result


def extract_segments_from_pdf(content: bytes) -> list[dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError('服务器未安装 pdfplumber，请执行 pip install pdfplumber') from exc

    collected: list[dict[str, Any]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                _, rows = parse_table_matrix(table)
                collected.extend(rows)
            if collected:
                continue
            text = page.extract_text() or ''
            collected.extend(_extract_segments_from_text(text))
    return finalize_segment_rows(collected)


def _extract_segments_from_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    patterns = [
        re.compile(r'(\d{2,3})\s+(\d{1,5})\s+(\d{1,6})'),
        re.compile(r'(\d{2,3})\s+(\d{1,6})'),
    ]
    for line in text.splitlines():
        line = line.strip()
        if not line or not re.search(r'\d', line):
            continue
        match3 = patterns[0].search(line)
        if match3:
            score, segment_count, cumulative = match3.groups()
            rows.append({
                'score': int(score),
                'segment_count': int(segment_count),
                'cumulative_rank': int(cumulative),
            })
            continue
        match2 = patterns[1].search(line)
        if match2:
            score, cumulative = match2.groups()
            rows.append({
                'score': int(score),
                'segment_count': None,
                'cumulative_rank': int(cumulative),
            })
    return rows


def extract_segments_from_spreadsheet(content: bytes, filename: str) -> list[dict[str, Any]]:
    matrix: list[list[Any]] = []
    lower = (filename or '').lower()
    if lower.endswith('.csv'):
        import csv
        text = content.decode('utf-8-sig', errors='replace')
        matrix = list(csv.reader(io.StringIO(text)))
    else:
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        worksheet = workbook.active
        matrix = [list(row) for row in worksheet.iter_rows(values_only=True)]
    _, parsed = parse_table_matrix(matrix)
    return finalize_segment_rows(parsed)


def extract_segments_from_file(content: bytes, filename: str) -> list[dict[str, Any]]:
    lower = (filename or '').lower()
    if lower.endswith('.pdf') or content[:4] == b'%PDF':
        return extract_segments_from_pdf(content)
    if lower.endswith(('.xlsx', '.xls', '.csv')):
        return extract_segments_from_spreadsheet(content, filename)
    raise ValueError('仅支持 PDF、Excel 或 CSV 格式的一分一段表')


def upsert_score_rank_table(
    *,
    province: str,
    year: int,
    batch: str = '',
    exam_type: str = '普通类',
    subject_type: str = '',
    title: str = '',
    source_file: str = '',
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_score_segment_tables()
    if not segments:
        raise ValueError('未能从文件中识别出一分一段数据，请检查表头是否含「分数」「累计人数/位次」等列')

    with get_connection() as connection:
        existing = row_to_dict(
            connection.execute(
                '''
                SELECT table_id FROM score_rank_tables
                WHERE province = ? AND year = ? AND batch = ? AND subject_type = ?
                ''',
                [province, year, batch or '', subject_type or ''],
            ).fetchone()
        )
        if existing:
            table_id = int(existing['table_id'])
            connection.execute(
                '''
                UPDATE score_rank_tables
                SET title = ?, source_file = ?, row_count = ?, exam_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE table_id = ?
                ''',
                [title or source_file, source_file, len(segments), exam_type, table_id],
            )
            connection.execute('DELETE FROM score_rank_segments WHERE table_id = ?', [table_id])
        else:
            cursor = connection.execute(
                '''
                INSERT INTO score_rank_tables (
                  province, year, batch, exam_type, subject_type, title, source_file, row_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [province, year, batch or '', exam_type, subject_type or '', title or source_file, source_file, len(segments)],
            )
            table_id = int(cursor.lastrowid)

        for item in segments:
            connection.execute(
                '''
                INSERT INTO score_rank_segments (table_id, score, segment_count, cumulative_rank)
                VALUES (?, ?, ?, ?)
                ''',
                [table_id, item['score'], item.get('segment_count'), item['cumulative_rank']],
            )
        connection.commit()
    return {
        'table_id': table_id,
        'province': province,
        'year': year,
        'batch': batch,
        'row_count': len(segments),
        'score_min': min(item['score'] for item in segments),
        'score_max': max(item['score'] for item in segments),
    }


def import_score_segment_file(
    content: bytes,
    filename: str,
    *,
    province: str,
    year: int,
    batch: str = '',
    exam_type: str = '普通类',
    subject_type: str = '',
    title: str = '',
) -> dict[str, Any]:
    segments = extract_segments_from_file(content, filename)
    return upsert_score_rank_table(
        province=province,
        year=year,
        batch=batch,
        exam_type=exam_type,
        subject_type=subject_type,
        title=title,
        source_file=filename,
        segments=segments,
    )


def find_score_rank_table(
    province: str,
    year: int | None = None,
    batch: str = '',
    subject_type: str = '',
) -> dict[str, Any] | None:
    ensure_score_segment_tables()
    sql = 'SELECT * FROM score_rank_tables WHERE province = ?'
    params: list[Any] = [province]
    if year:
        sql += ' AND year = ?'
        params.append(year)
    if batch:
        sql += ' AND batch = ?'
        params.append(batch)
    if subject_type:
        sql += ' AND subject_type = ?'
        params.append(subject_type)
    sql += ' ORDER BY year DESC, table_id DESC LIMIT 1'
    with get_connection() as connection:
        return row_to_dict(connection.execute(sql, params).fetchone())


def lookup_rank_by_score(
    province: str,
    score: int,
    *,
    year: int | None = None,
    batch: str = '',
    subject_type: str = '',
) -> int | None:
    table = find_score_rank_table(province, year, batch, subject_type)
    if not table:
        return None
    with get_connection() as connection:
        exact = row_to_dict(
            connection.execute(
                '''
                SELECT cumulative_rank FROM score_rank_segments
                WHERE table_id = ? AND score = ?
                ''',
                [table['table_id'], int(score)],
            ).fetchone()
        )
        if exact:
            return int(exact['cumulative_rank'])
        lower = row_to_dict(
            connection.execute(
                '''
                SELECT score, cumulative_rank FROM score_rank_segments
                WHERE table_id = ? AND score <= ?
                ORDER BY score DESC
                LIMIT 1
                ''',
                [table['table_id'], int(score)],
            ).fetchone()
        )
        if lower:
            return int(lower['cumulative_rank'])
        higher = row_to_dict(
            connection.execute(
                '''
                SELECT score, cumulative_rank FROM score_rank_segments
                WHERE table_id = ? AND score >= ?
                ORDER BY score ASC
                LIMIT 1
                ''',
                [table['table_id'], int(score)],
            ).fetchone()
        )
        if higher:
            return int(higher['cumulative_rank'])
    return None


def lookup_score_by_rank(
    province: str,
    rank: int,
    *,
    year: int | None = None,
    batch: str = '',
    subject_type: str = '',
) -> int | None:
    table = find_score_rank_table(province, year, batch, subject_type)
    if not table:
        return None
    with get_connection() as connection:
        row = row_to_dict(
            connection.execute(
                '''
                SELECT score, cumulative_rank FROM score_rank_segments
                WHERE table_id = ? AND cumulative_rank >= ?
                ORDER BY cumulative_rank ASC, score DESC
                LIMIT 1
                ''',
                [table['table_id'], int(rank)],
            ).fetchone()
        )
        if row:
            return int(row['score'])
    return None


def list_score_rank_tables(limit: int = 50) -> list[dict[str, Any]]:
    ensure_score_segment_tables()
    with get_connection() as connection:
        return rows_to_dicts(
            connection.execute(
                'SELECT * FROM score_rank_tables ORDER BY year DESC, province ASC, table_id DESC LIMIT ?',
                [int(limit)],
            ).fetchall()
        )
