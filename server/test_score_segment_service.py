import unittest

from score_segment_service import (
    detect_score_header_row_index,
    finalize_segment_rows,
    infer_subject_type_from_combination,
    parse_columnar_segments,
    parse_segments_from_matrix,
    parse_table_matrix,
    validate_segment_rows,
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

    def test_parse_columnar_without_header(self):
        table = [
            [669, 162, 2741, 2025, '物理类'],
            [668, 198, 2903, 2025, '物理类'],
            [650, 180, 8281, 2025, '物理类'],
        ]
        rows, meta = parse_columnar_segments(table)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['score'], 669)
        self.assertEqual(rows[0]['cumulative_rank'], 2741)
        self.assertEqual(rows[2]['cumulative_rank'], 8281)
        self.assertEqual(meta['year'], 2025)
        self.assertEqual(meta['subject_type'], '物理')

    def test_parse_segments_from_matrix_prefers_header(self):
        table = [
            ['分数', '本段人数', '累计人数'],
            ['680', '42', '120'],
        ]
        rows, meta = parse_segments_from_matrix(table)
        self.assertEqual(len(rows), 1)
        self.assertEqual(meta, {})

    def test_parse_segments_from_matrix_falls_back_to_columnar(self):
        table = [
            [669, 162, 2741, 2025, '物理类'],
            [668, 198, 2903, 2025, '物理类'],
        ]
        rows, meta = parse_segments_from_matrix(table)
        self.assertEqual(len(rows), 2)
        self.assertEqual(meta['subject_type'], '物理')

    def test_validate_rejects_inflated_cumulative(self):
        rows = [
            {'score': 680, 'segment_count': 100, 'cumulative_rank': 50000},
            {'score': 679, 'segment_count': 100, 'cumulative_rank': 50100},
        ] * 6
        with self.assertRaises(ValueError):
            validate_segment_rows(rows)


if __name__ == '__main__':
    unittest.main()
