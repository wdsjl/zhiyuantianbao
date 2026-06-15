import unittest

from recommend_pool_service import compute_preference_score


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


if __name__ == '__main__':
    unittest.main()
