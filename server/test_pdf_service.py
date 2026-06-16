import unittest

from pdf_service import (
    PORTRAIT_LINE_WIDTH,
    build_draft_pdf,
    build_text_report_pdf,
    display_width,
    format_admission_2025_display,
    format_markdown_for_pdf,
    format_volunteer_item_block,
    lines_from_paragraphs,
    pad_column,
    truncate_display_text,
)


class PdfServiceTests(unittest.TestCase):
    def test_pad_column_aligns_ascii_and_cjk(self):
        self.assertEqual(display_width('中国'), 4)
        self.assertEqual(len(pad_column('冲', 4)), 3)

    def test_each_volunteer_has_exactly_four_lines(self):
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
            'risk_reason': '当前志愿结构相对稳妥，仍需以考试院和高校官方信息为准。',
        })
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith('【45】保'))
        self.assertTrue(lines[1].startswith('专业：'))
        self.assertIn('2025录取：暂无分 / 位次暂无', lines[2])
        self.assertIn('城市：哈尔滨市', lines[2])
        self.assertIn('学费：3500', lines[2])
        self.assertIn('学制：四年', lines[2])
        self.assertIn('调剂：是', lines[2])
        self.assertIn('风险：低', lines[2])
        self.assertTrue(lines[3].startswith('说明：'))

    def test_risk_on_third_line_not_split(self):
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
        self.assertIn('2025录取：653分 / 位次2100', lines[2])
        self.assertIn('风险：中', lines[2])
        self.assertNotIn('险：', lines[3])

    def test_format_admission_2025_display(self):
        self.assertEqual(format_admission_2025_display(None, None), '暂无分 / 位次暂无')
        self.assertEqual(format_admission_2025_display(653, 2100), '653分 / 位次2100')
        self.assertEqual(format_admission_2025_display(653, None), '653分 / 位次暂无')

    def test_truncate_display_text(self):
        text = truncate_display_text('一二三四五六七八九十', 8)
        self.assertLessEqual(display_width(text), 8)

    def test_format_markdown_for_pdf_strips_syntax(self):
        text = format_markdown_for_pdf('## 一、兴趣画像\n\n- **设计学类**：适合创意\n1. **建筑学**')
        self.assertNotIn('**', text)
        self.assertNotIn('##', text)
        self.assertIn('一、兴趣画像', text)
        self.assertIn('· 设计学类', text)

    def test_lines_from_paragraphs_respects_display_width(self):
        body = '本报告旨在帮助您理清志愿填报思路，结合霍兰德兴趣测评与成绩定位，给出院校与专业方向建议。' * 3
        lines = lines_from_paragraphs(body, PORTRAIT_LINE_WIDTH)
        self.assertTrue(lines)
        for line in lines:
            if line.strip():
                self.assertLessEqual(display_width(line), PORTRAIT_LINE_WIDTH)

    def test_build_text_report_pdf_returns_portrait_bytes(self):
        pdf = build_text_report_pdf(
            '智愿填报 · 霍兰德职业兴趣深度报告',
            {
                'name': '测试同学',
                'province': '河南',
                'subject_combination': '历史+政治+地理',
                'score': 600,
                'rank': 11060,
                'target_batch': '本科批',
            },
            '## 一、兴趣画像\n\n**现实型（R）**与**研究型（I）**组合突出，适合需要动手与分析并重的专业方向。',
        )
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn(b'/MediaBox [0 0 595 842]', pdf)
        self.assertGreater(len(pdf), 1000)

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
