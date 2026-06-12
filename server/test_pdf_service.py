import unittest

from pdf_service import (
    build_draft_pdf,
    display_width,
    format_volunteer_table_header,
    format_volunteer_table_row,
    pad_column,
)


class PdfServiceTests(unittest.TestCase):
    def test_pad_column_aligns_ascii_and_cjk(self):
        self.assertEqual(display_width('中国'), 4)
        self.assertEqual(len(pad_column('冲', 4)), 3)

    def test_volunteer_table_row_keeps_columns_on_one_line(self):
        row_lines = format_volunteer_table_row({
            'sort_order': 1,
            'gradient_type': '冲',
            'school_code': '10423',
            'school_name': '中国海洋大学',
            'major_code': '120204',
            'major_name': '财务管理',
            'city': '青岛市',
            'tuition': 6600,
            'duration': '四年',
            'is_adjustable': 1,
            'risk_level': '中',
        })
        self.assertEqual(len(row_lines), 1)
        line = row_lines[0]
        self.assertIn('6600', line)
        self.assertIn('四年', line)
        self.assertIn('是', line)
        self.assertIn('中', line)

    def test_build_draft_pdf_returns_landscape_bytes(self):
        pdf = build_draft_pdf(
            {'draft_name': '测试', 'score': 693, 'rank': 2000, 'province': '河南', 'batch': '本科批', 'year': 2026},
            {'name': '测试同学', 'province': '河南', 'subject_combination': '物理+化学+生物', 'target_batch': '本科批'},
            [{
                'sort_order': 1,
                'gradient_type': '冲',
                'school_code': '10423',
                'school_name': '中国海洋大学',
                'major_code': '120204',
                'major_name': '财务管理',
                'city': '青岛市',
                'tuition': 6600,
                'duration': '四年',
                'is_adjustable': 1,
                'risk_level': '中',
                'risk_reason': '院校往年录取位次高于当前位次，建议保留稳妥志愿兜底。',
            }],
        )
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn(b'/MediaBox [0 0 842 595]', pdf)
        self.assertGreater(len(pdf), 1000)


if __name__ == '__main__':
    unittest.main()
