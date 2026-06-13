import unittest

from score_segment_service import (
    finalize_segment_rows,
    parse_table_matrix,
)


class ScoreSegmentServiceTests(unittest.TestCase):
    def test_parse_table_with_cumulative(self):
        table = [
            ['分数', '本段人数', '累计人数'],
            ['680', '42', '120'],
            ['679', '35', '155'],
            ['678', '28', '183'],
        ]
        _, rows = parse_table_matrix(table)
        finalized = finalize_segment_rows(rows)
        self.assertEqual(len(finalized), 3)
        self.assertEqual(finalized[0]['score'], 680)
        self.assertEqual(finalized[0]['cumulative_rank'], 120)

    def test_finalize_from_segment_counts(self):
        rows = [
            {'score': 680, 'segment_count': 10, 'cumulative_rank': None},
            {'score': 679, 'segment_count': 20, 'cumulative_rank': None},
        ]
        finalized = finalize_segment_rows(rows)
        self.assertEqual(finalized[0]['cumulative_rank'], 10)
        self.assertEqual(finalized[1]['cumulative_rank'], 30)


if __name__ == '__main__':
    unittest.main()
