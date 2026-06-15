import unittest

from recommend_service import (
    build_rank_windows,
    build_weighted_items,
    expand_batch_aliases,
    fetch_recommendation_candidates,
    list_province_admission_batches,
    province_variants,
)


class RecommendServiceTests(unittest.TestCase):
    def test_build_weighted_items_dedupes_school_major(self):
        rows = [
            {'school_id': 1, 'major_id': 10, 'year': 2025, 'min_rank': 1000, 'min_score': 600},
            {'school_id': 1, 'major_id': 10, 'year': 2024, 'min_rank': 1100, 'min_score': 590},
            {'school_id': 2, 'major_id': 20, 'year': 2025, 'min_rank': 2000, 'min_score': 580},
        ]
        items = build_weighted_items(rows)
        self.assertEqual(len(items), 2)
        self.assertIn('weighted_rank', items[0])

    def test_build_weighted_items_includes_2025_stats(self):
        rows = [
            {'school_id': 1, 'major_id': 10, 'year': 2025, 'min_rank': 2600, 'min_score': 680},
            {'school_id': 1, 'major_id': 10, 'year': 2024, 'min_rank': 2700, 'min_score': 675},
        ]
        items = build_weighted_items(rows)
        self.assertEqual(items[0]['admission_score_2025'], 680)
        self.assertEqual(items[0]['admission_rank_2025'], 2600)

    def test_build_rank_windows_includes_relaxed_and_unbounded(self):
        windows = build_rank_windows(2600, 'mid', '本科批')
        self.assertGreater(len(windows), 1)
        self.assertEqual(windows[-1], (None, None))

    def test_fetch_candidates_returns_meta(self):
        items, batch, meta = fetch_recommendation_candidates(
            '河南',
            '本科批',
            '物理,化学,生物',
            48,
            rule_batch='本科批',
            user_rank=2600,
            segment='mid',
        )
        self.assertEqual(batch, '本科批')
        self.assertIn('candidate_pool', meta)
        self.assertIn('available_batches', meta)
        self.assertIn('rank_window_relaxed', meta)
        self.assertIsInstance(items, list)

    def test_province_variants_include_short_and_full_name(self):
        variants = province_variants('河南省')
        self.assertIn('河南', variants)
        self.assertIn('河南省', variants)

    def test_list_province_batches_returns_list(self):
        rows = list_province_admission_batches('河南')
        self.assertIsInstance(rows, list)

    def test_expand_batch_aliases_for_undergraduate(self):
        aliases = expand_batch_aliases('本科批')
        self.assertIn('本科批', aliases)
        self.assertIn('本科', aliases)
        self.assertIn('本科一批', aliases)


if __name__ == '__main__':
    unittest.main()
