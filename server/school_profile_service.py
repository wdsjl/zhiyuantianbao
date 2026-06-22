"""院校扩展信息：保研率、招生章程链接等。"""
from __future__ import annotations

import re
from typing import Any

from db import get_connection, row_to_dict

SCHOOL_PROFILE_FIELDS = ('postgraduate_rate', 'regulation_url', 'regulation_year', 'website')


def ensure_school_profile_columns() -> None:
    with get_connection() as connection:
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(schools)').fetchall()}
        migrations = {
            'postgraduate_rate': 'ALTER TABLE schools ADD COLUMN postgraduate_rate TEXT',
            'regulation_url': 'ALTER TABLE schools ADD COLUMN regulation_url TEXT',
            'regulation_year': 'ALTER TABLE schools ADD COLUMN regulation_year INTEGER',
        }
        for name, sql in migrations.items():
            if name not in columns:
                connection.execute(sql)
        connection.commit()


def infer_regulation_year(header: str) -> int:
    text = str(header or '')
    if '2026' in text:
        return 2026
    if '2025' in text and '招生章程' in text:
        return 2026
    match = re.search(r'20\d{2}', text)
    return int(match.group()) if match else 2026


def normalize_postgraduate_rate(value: Any) -> str:
    if value in (None, ''):
        return ''
    text = str(value).strip()
    if not text:
        return ''
    if text.endswith('%'):
        return text
    try:
        number = float(text)
        if 0 < number <= 1:
            number *= 100
        return f'{number:g}%'
    except ValueError:
        return text


def enrich_school_profile(school: dict[str, Any] | None) -> dict[str, Any] | None:
    if not school:
        return school
    ensure_school_profile_columns()
    if school.get('regulation_url'):
        school.setdefault('regulation_year', school.get('regulation_year') or 2026)
        school['has_regulation'] = True
        return school

    school_id = school.get('school_id')
    if not school_id:
        return school

    with get_connection() as connection:
        brochure = row_to_dict(connection.execute(
            '''
            SELECT source_url, year, title FROM admission_brochures
            WHERE school_id = ? AND source_url IS NOT NULL AND source_url != ''
            ORDER BY year DESC, brochure_id DESC LIMIT 1
            ''',
            [int(school_id)],
        ).fetchone())

    if brochure and brochure.get('source_url'):
        school['regulation_url'] = brochure['source_url']
        school['regulation_year'] = brochure.get('year') or 2026
        school['regulation_title'] = brochure.get('title') or ''
        school['regulation_source'] = 'brochure_archive'
    school['has_regulation'] = bool(school.get('regulation_url'))
    return school


def school_profile_updates(row: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field in SCHOOL_PROFILE_FIELDS:
        value = row.get(field)
        if value in (None, ''):
            continue
        if field == 'postgraduate_rate':
            updates[field] = normalize_postgraduate_rate(value)
        elif field == 'regulation_year':
            updates[field] = int(value)
        else:
            updates[field] = str(value).strip()
    return updates
