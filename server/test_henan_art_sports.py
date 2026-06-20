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


if __name__ == '__main__':
    unittest.main()
