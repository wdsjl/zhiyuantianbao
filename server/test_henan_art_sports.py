"""河南艺体综合分与冲稳保匹配测试。"""

import unittest

from db import get_connection
from henan_art_sports_service import (
    calc_art_composite,
    calc_sports_composite,
    calculate_composite,
    check_dual_line,
    default_formula_id,
    get_meta,
    load_from_admission_records,
    match_schools,
    resolve_school_major_ids,
)


class HenanArtSportsTests(unittest.TestCase):
    def test_art_formula_five_default(self) -> None:
        # 0.5*500 + 1.25*240 = 550
        self.assertEqual(calc_art_composite(500, 240, 5), 550.0)

    def test_sports_formula_three_default(self) -> None:
        # 0.5*500 + 2.5*120 = 550
        self.assertEqual(calc_sports_composite(500, 120, 3), 550.0)

    def test_default_formula_ids(self) -> None:
        self.assertEqual(default_formula_id('艺术类', '本科'), 5)
        self.assertEqual(default_formula_id('体育类', '专科'), 3)

    def test_meta_volunteer_rule_art_undergrad(self) -> None:
        meta = get_meta()
        self.assertEqual(meta['volunteer_slots'], 64)
        self.assertEqual(meta['volunteer_mode'], '专业+院校')
        self.assertIn('艺术本科批', meta['volunteer_rule_description'])
        self.assertIn('专业+院校', meta['volunteer_rule_description'])

    def test_dual_line_check(self) -> None:
        ok = check_dual_line(420, 200, 400, 180, '艺术类')
        self.assertTrue(ok['dual_line_ok'])
        fail = check_dual_line(390, 200, 400, 180, '艺术类')
        self.assertFalse(fail['dual_line_ok'])

    def test_waive_switches_to_normal_track(self) -> None:
        result = calculate_composite({
            'category': '艺术类',
            'culture_score': 520,
            'professional_score': 250,
            'waive_art_sports_batch': True,
        })
        self.assertTrue(result['use_normal_track'])
        self.assertEqual(result['composite_score'], 520)

    def test_match_blocks_undergraduate_without_dual_line(self) -> None:
        result = match_schools({
            'category': '艺术类',
            'culture_score': 300,
            'professional_score': 100,
            'formula_id': 5,
            'batch_level': '本科',
            'culture_cutoff': 400,
            'pro_cutoff': 180,
        })
        self.assertFalse(result['eligible'])
        self.assertEqual(result['groups']['rush'], [])

    def test_match_returns_groups_when_eligible(self) -> None:
        result = match_schools({
            'category': '艺术类',
            'culture_score': 500,
            'professional_score': 250,
            'formula_id': 5,
            'batch_level': '本科',
            'culture_cutoff': 350,
            'pro_cutoff': 180,
        })
        self.assertTrue(result['eligible'])
        total = len(result['groups']['rush']) + len(result['groups']['steady']) + len(result['groups']['safe'])
        self.assertGreater(total, 0)

    def test_is_art_sports_request(self) -> None:
        from henan_art_sports_service import is_art_sports_request, query_art_sports_eligible_pool, build_art_sports_recommendation
        self.assertTrue(is_art_sports_request({
            'province': '河南',
            'exam_type': '艺术类',
            'score': 500,
            'professional_score': 250,
            'batch': '艺术本科批',
        }))
        self.assertFalse(is_art_sports_request({
            'province': '河南',
            'exam_type': '艺术类',
            'waive_art_sports_batch': True,
            'score': 500,
            'batch': '艺术本科批',
        }))
        pool = query_art_sports_eligible_pool({
            'province': '河南',
            'exam_type': '艺术类',
            'score': 520,
            'professional_score': 250,
            'batch': '艺术本科批',
            'art_sports_formula_id': 5,
            'culture_cutoff': 350,
            'pro_cutoff': 180,
        })
        self.assertTrue(pool['art_sports_mode'])
        self.assertGreater(pool['summary']['total'], 0)
        plan = build_art_sports_recommendation({
            'province': '河南',
            'exam_type': '艺术类',
            'score': 520,
            'professional_score': 250,
            'batch': '艺术本科批',
            'art_sports_formula_id': 5,
            'culture_cutoff': 350,
            'pro_cutoff': 180,
            'rank': 10000,
            'subject_combination': '物理+化学+生物',
        })
        self.assertTrue(plan['art_sports_mode'])
        self.assertGreater(len(plan['items']), 0)

    def test_load_from_admission_records(self) -> None:
        school_name = '单元测试艺术大学AS'
        major_name = '单元测试专业AS'
        school_id, major_id = resolve_school_major_ids(school_name, major_name, '艺术类')
        batch = '艺术本科批'
        with get_connection() as connection:
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS enrollment_plans (
                  plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  year INTEGER NOT NULL,
                  province TEXT NOT NULL,
                  batch TEXT NOT NULL,
                  school_id INTEGER NOT NULL,
                  school_code TEXT NOT NULL,
                  major_id INTEGER NOT NULL,
                  major_code TEXT NOT NULL,
                  major_name TEXT NOT NULL,
                  subject_requirement TEXT,
                  enrollment_count INTEGER,
                  tuition INTEGER,
                  duration TEXT,
                  campus TEXT,
                  special_notes TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE (year, province, batch, school_id, major_id)
                )
                '''
            )
            connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS admission_records (
                  admission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  year INTEGER NOT NULL,
                  province TEXT NOT NULL,
                  batch TEXT NOT NULL,
                  school_id INTEGER NOT NULL,
                  school_code TEXT NOT NULL,
                  major_id INTEGER NOT NULL,
                  major_code TEXT NOT NULL,
                  min_score INTEGER,
                  min_rank INTEGER,
                  avg_score INTEGER,
                  avg_rank INTEGER,
                  max_score INTEGER,
                  max_rank INTEGER,
                  enrollment_count INTEGER,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE (year, province, batch, school_id, major_id)
                )
                '''
            )
            for year, score in ((2025, 520), (2024, 510), (2023, 500)):
                connection.execute(
                    '''
                    INSERT OR REPLACE INTO admission_records
                    (year, province, batch, school_id, school_code, major_id, major_code, min_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    [year, '河南', batch, school_id, f'S{school_id}', major_id, f'M{major_id}', score],
                )
            connection.commit()
        rows = load_from_admission_records({
            'province': '河南',
            'exam_type': '艺术类',
            'batch': batch,
            'art_sports_formula_id': 5,
        })
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['school_name'], school_name)
        self.assertEqual(rows[0]['data_source'], 'admission_records')
        self.assertGreater(rows[0]['ref_min_composite'], 500)
        with get_connection() as connection:
            connection.execute(
                'DELETE FROM admission_records WHERE school_id = ? AND major_id = ?',
                [school_id, major_id],
            )
            connection.commit()

    def test_import_art_sports_rows(self) -> None:
        try:
            from import_service import import_art_sports_rows
        except ModuleNotFoundError:
            self.skipTest('openpyxl not installed')
        result = import_art_sports_rows('test.csv', [{
            'province': '河南',
            'category': '艺术类',
            'batch_level': '本科',
            'school_name': '测试艺术大学',
            'major_name': '测试专业',
            'formula_id': 5,
            'min_composite_2025': 500.0,
            'min_composite_2024': 495.0,
            'min_composite_2023': 490.0,
            'city': '郑州',
        }])
        self.assertGreaterEqual(result['success_count'], 1)


if __name__ == '__main__':
    unittest.main()
