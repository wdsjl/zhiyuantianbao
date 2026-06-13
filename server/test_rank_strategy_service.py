import unittest

from rank_strategy_service import (
    assemble_recommendation_plan,
    classify_gradient,
    filter_rank_eligible_candidates,
    get_plan_quotas,
    is_candidate_match_for_user,
    is_plausible_admission_pair,
    resolve_school_rank,
)


def _candidate(school_id: int, major_id: int, school_name: str, min_rank: int | None) -> dict:
    return {
        'school_id': school_id,
        'major_id': major_id,
        'school_name': school_name,
        'min_rank': min_rank,
        'weighted_rank': min_rank,
    }


class RankStrategyServiceTests(unittest.TestCase):
    def test_null_rank_classified_as_dian_not_wen(self):
        self.assertEqual(classify_gradient(2000, None, 'high', '本科批'), '垫')

    def test_high_rank_student_excludes_low_tier_schools(self):
        candidates = [
            _candidate(1, 1, '浙江大学医学院', 1800),
            _candidate(2, 2, '华中科技大学', 1950),
            _candidate(3, 3, '西京学院', 85000),
            _candidate(4, 4, '安阳工学院', 92000),
            _candidate(5, 5, '武汉大学', 2100),
            _candidate(6, 6, '中山大学', 2050),
            _candidate(7, 7, '西安交通大学', 2200),
            _candidate(8, 8, '北京理工大学', 1900),
            _candidate(9, 9, '同济大学', 2150),
        ]
        filtered = filter_rank_eligible_candidates(candidates, 2000, 'high', '本科批', min_required=5)
        names = {item['school_name'] for item in filtered}
        self.assertIn('浙江大学医学院', names)
        self.assertNotIn('西京学院', names)
        self.assertNotIn('安阳工学院', names)

    def test_assemble_plan_respects_rank_window(self):
        candidates = [
            _candidate(i, i, f'名校{i}', 1800 + i * 20)
            for i in range(1, 12)
        ] + [
            _candidate(100, 100, '西京学院', 85000),
            _candidate(101, 101, '安阳工学院', 92000),
        ]
        selected, meta = assemble_recommendation_plan(
            candidates,
            user_rank=2000,
            plan_style='balanced',
            batch='本科批',
            segment='high',
            total_slots=9,
        )
        self.assertEqual(len(selected), 9)
        names = {row['school_name'] for row in selected}
        self.assertNotIn('西京学院', names)
        self.assertNotIn('安阳工学院', names)
        self.assertGreater(meta['candidate_pool_after_filter'], 0)

    def test_max_majors_per_school_limits_duplicates(self):
        candidates = [
            _candidate(1, major_id, '湖南女子学院', 2000 + major_id)
            for major_id in range(1, 8)
        ]
        selected, _ = assemble_recommendation_plan(
            candidates,
            user_rank=2000,
            batch='本科批',
            segment='high',
            total_slots=9,
            max_majors_per_school=2,
        )
        school_counts = {}
        for row in selected:
            school_counts[row['school_id']] = school_counts.get(row['school_id'], 0) + 1
        self.assertLessEqual(max(school_counts.values()), 2)

    def test_resolve_school_rank_prefers_weighted(self):
        item = {'weighted_rank': 1500, 'min_rank': 3000}
        self.assertEqual(resolve_school_rank(item), 1500)

    def test_reject_implausible_score_rank_pair(self):
        self.assertFalse(is_plausible_admission_pair(2500, 480))
        self.assertFalse(is_plausible_admission_pair(85000, 680))

    def test_high_score_user_rejects_xijing_dirty_data(self):
        dirty = _candidate(3, 3, '西京学院', 2500)
        dirty['min_score'] = 480
        dirty['weighted_score'] = 480
        self.assertFalse(is_candidate_match_for_user(dirty, 2000, 693, 'high', '本科批'))

    def test_get_plan_quotas_scales_to_province_slots(self):
        quotas = get_plan_quotas('balanced', '本科批', 48)
        self.assertEqual(sum(quotas.values()), 48)
        self.assertGreater(quotas['稳'], quotas['冲'])

    def test_assemble_excludes_dirty_low_score_schools(self):
        candidates = [
            _candidate(i, i, f'名校{i}', 1800 + i * 20)
            for i in range(1, 12)
        ]
        dirty = _candidate(99, 99, '西京学院', 2500)
        dirty['min_score'] = 480
        dirty['weighted_score'] = 480
        candidates.append(dirty)
        selected, _ = assemble_recommendation_plan(
            candidates,
            user_rank=2000,
            user_score=693,
            batch='本科批',
            segment='high',
            total_slots=9,
        )
        names = {row['school_name'] for row in selected}
        self.assertNotIn('西京学院', names)


if __name__ == '__main__':
    unittest.main()
