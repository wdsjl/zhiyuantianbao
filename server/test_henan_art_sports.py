"""河南艺体综合分与冲稳保匹配测试。"""

import unittest

from henan_art_sports_service import (
    calc_art_composite,
    calc_sports_composite,
    calculate_composite,
    check_dual_line,
    default_formula_id,
    match_schools,
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
