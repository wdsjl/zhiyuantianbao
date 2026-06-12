import unittest

from pdf_service import (
    build_draft_pdf,
    display_width,
    format_volunteer_item_block,
    pad_column,
)


class PdfServiceTests(unittest.TestCase):
    def test_pad_column_aligns_ascii_and_cjk(self):
        self.assertEqual(display_width('中国'), 4)
        self.assertEqual(len(pad_column('冲', 4)), 3)

    def test_volunteer_item_block_contains_key_fields(self):
        lines = format_volunteer_item_block({
            'sort_order': 1,
            'gradient_type': '冲',
            'school_code': '10423',
            'school_name': '中国海洋大学',
            'major_code': '120204',
            'major_name': '财务管理',
            'admission_score_2025': 653,
            'admission_rank_2025': 2100,
            'city': '青岛市',
            'tuition': 6600,
            'duration': '四年',
            'is_adjustable': 1,
            'risk_level': '中',
            'risk_reason': '院校往年录取位次高于当前位次，建议保留稳妥志愿兜底。',
        })
        merged = '\n'.join(lines)
        self.assertIn('【1】冲', merged)
        self.assertIn('653', merged)
        self.assertIn('2100', merged)
        self.assertIn('6600', merged)
        self.assertIn('四年', merged)

    def test_risk_label_not_split_across_lines(self):
        lines = format_volunteer_item_block({
            'sort_order': 45,
            'gradient_type': '保',
            'school_code': '10240',
            'school_name': '哈尔滨商业大学',
            'major_code': '020301K',
            'major_name': '金融学（中外合作办学）',
            'admission_score_2025': None,
            'admission_rank_2025': None,
            'city': '哈尔滨市',
            'tuition': 3500,
            'duration': '四年',
            'is_adjustable': 1,
            'risk_level': '低',
        })
        for line in lines:
            self.assertFalse(line.endswith('风'))
            self.assertNotEqual(line.strip(), '险：低')
            if '风险' in line:
                self.assertIn('风险：低', line)

    def test_long_major_wraps_without_breaking_other_fields(self):
        lines = format_volunteer_item_block({
            'sort_order': 4,
            'gradient_type': '冲',
            'school_code': '10054',
            'school_name': '华北电力大学',
            'major_code': '120201',
            'major_name': '工商管理（含会计学、财务管理、市场营销等多个专业方向，保定校区就读）',
            'admission_score_2025': None,
            'admission_rank_2025': None,
            'city': '北京市',
            'tuition': 5000,
            'duration': '四年',
            'is_adjustable': 1,
            'risk_level': '中',
        })
        merged = '\n'.join(lines)
        self.assertIn('2025录取：暂无分 / 位次暂无', merged)
        self.assertIn('城市：北京市', merged)

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
                'admission_score_2025': 653,
                'admission_rank_2025': 2100,
            }],
        )
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn(b'/MediaBox [0 0 842 595]', pdf)
        self.assertGreater(len(pdf), 1000)


if __name__ == '__main__':
    unittest.main()
