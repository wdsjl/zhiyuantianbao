import unittest

from score_segment_service import (
    detect_score_header_row_index,
    finalize_segment_rows,
    infer_subject_type_from_combination,
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


    def test_detect_header_skips_title_rows(self):
        table = [
            ['河南省2025年普通类一分一段表'],
            ['物理类'],
            ['分数', '本段人数', '累计人数'],
            ['680', '42', '120'],
        ]
        self.assertEqual(detect_score_header_row_index(table), 2)

    def test_infer_subject_type_from_combination(self):
        self.assertEqual(infer_subject_type_from_combination('物理,化学,生物'), '物理')
        self.assertEqual(infer_subject_type_from_combination('历史,政治,地理'), '历史')


if __name__ == '__main__':
    unittest.main()
