"""院校保研率与招生章程导入测试。"""
from __future__ import annotations

import unittest

from db import get_connection
from school_profile_service import (
    enrich_school_profile,
    ensure_school_profile_columns,
    infer_regulation_year,
    normalize_postgraduate_rate,
    school_profile_updates,
)


class SchoolProfileImportTests(unittest.TestCase):
    def test_infer_regulation_year_from_2025_header(self) -> None:
        self.assertEqual(infer_regulation_year('2025招生章程'), 2026)
        self.assertEqual(infer_regulation_year('2026招生章程'), 2026)

    def test_normalize_postgraduate_rate(self) -> None:
        self.assertEqual(normalize_postgraduate_rate('12.5'), '12.5%')
        self.assertEqual(normalize_postgraduate_rate('8%'), '8%')

    def test_school_profile_updates(self) -> None:
        updates = school_profile_updates({
            'postgraduate_rate': '15',
            'regulation_url': 'https://gaokao.chsi.com.cn/zsgs/zhangcheng/listZszc--schId-1.dhtml',
            'regulation_year': 2026,
        })
        self.assertEqual(updates['postgraduate_rate'], '15%')
        self.assertIn('gaokao.chsi.com.cn', updates['regulation_url'])

    def test_persist_school_profile_columns(self) -> None:
        ensure_school_profile_columns()
        with get_connection() as connection:
            cursor = connection.execute(
                '''
                INSERT INTO schools (
                  school_code, school_name, province, postgraduate_rate, regulation_url, regulation_year
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''',
                [
                    'TESTREG001',
                    '测试章程大学',
                    '河南',
                    '12.5%',
                    'https://gaokao.chsi.com.cn/zsgs/zhangcheng/listZszc--schId-1.dhtml',
                    2026,
                ],
            )
            school_id = cursor.lastrowid
            connection.commit()
            school = connection.execute('SELECT * FROM schools WHERE school_id = ?', [school_id]).fetchone()
        enriched = enrich_school_profile(dict(school))
        self.assertTrue(enriched['has_regulation'])
        self.assertEqual(enriched['regulation_year'], 2026)

        with get_connection() as connection:
            connection.execute('DELETE FROM schools WHERE school_code = ?', ['TESTREG001'])
            connection.commit()


if __name__ == '__main__':
    unittest.main()
