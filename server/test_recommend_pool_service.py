import unittest

from recommend_pool_service import build_empty_pool_hint, compute_preference_score
from schemas import RecommendRequest


class RecommendPoolPreferenceTests(unittest.TestCase):
    def test_preferred_city_boosts_score(self):
        row = {'city': '郑州', 'major_type': '计算机类', 'major_name': '软件工程', 'school_name': '郑州大学'}
        score = compute_preference_score(
            row,
            {'preferredCities': ['郑州'], 'preferredMajorTypes': ['计算机类']},
            ['计算机类'],
        )
        self.assertGreaterEqual(score, 7)

    def test_avoid_direction_excludes_candidate(self):
        row = {'city': '北京', 'major_type': '医学类', 'major_name': '临床医学', 'school_name': '某医学院'}
        score = compute_preference_score(row, {'avoidDirections': ['医学']}, [])
        self.assertEqual(score, -1000)

    def test_empty_pool_hint_for_missing_history_data(self):
        request = RecommendRequest(
            province='河南',
            batch='本科批',
            score=600,
            rank=6178,
            subject_combination='历史+政治+地理',
        )
        hint = build_empty_pool_hint(
            request,
            {'total_cnt': 19912, 'history_cnt': 0, 'physics_cnt': 18000, 'open_cnt': 1912},
        )
        self.assertIn('历史类', hint)
        self.assertIn('物理类', hint)


if __name__ == '__main__':
    unittest.main()
