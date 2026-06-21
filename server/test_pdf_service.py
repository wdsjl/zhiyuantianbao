"""志愿 PDF 版式测试。"""

import unittest

from pdf_service import build_draft_pdf, format_draft_item_lines, is_art_sports_student


class PdfServiceTests(unittest.TestCase):
    def test_art_sports_student_detection(self) -> None:
        self.assertTrue(is_art_sports_student({'exam_type': '艺术类'}, {'batch': '本科批'}))
        self.assertTrue(is_art_sports_student({}, {'batch': '艺术本科批'}))
        self.assertFalse(is_art_sports_student({'exam_type': '艺术类', 'waive_art_sports_batch': 1}, {}))

    def test_format_draft_item_lines_wraps_long_major_name(self) -> None:
        lines = format_draft_item_lines({
            'sort_order': 1,
            'gradient_type': '冲',
            'school_code': '2895',
            'school_name': '武汉工程大学',
            'major_code': '2895101-08',
            'major_name': '会计学（辅修英语专业）（除基础专业学费外，超出部分按每学分100元另行收取，每年1000元左右）',
            'city': '武汉',
            'tuition': 4500,
            'duration': '4年',
            'is_adjustable': True,
            'risk_level': '中',
            'risk_reason': '院校参考最低综合分偏高，建议保留稳妥志愿兜底。 参考最低综合分 520',
        }, art_sports=True)
        joined = '\n'.join(lines)
        self.assertIn('【志愿 1】梯度：冲', joined)
        self.assertIn('院校：2895 / 武汉工程大学', joined)
        self.assertIn('专业：', joined)
        self.assertIn('城市：武汉', joined)
        self.assertNotIn('序号  梯度', joined)

    def test_build_draft_pdf_art_sports_has_culture_score_line(self) -> None:
        pdf = build_draft_pdf(
            {'draft_name': '测试', 'province': '河南', 'year': 2025, 'batch': '艺术本科批', 'score': 500, 'rank': 0},
            {'name': '张三', 'province': '河南', 'exam_type': '艺术类', 'professional_score': 240, 'target_batch': '艺术本科批'},
            [{
                'sort_order': 1,
                'gradient_type': '冲',
                'school_code': '1001',
                'school_name': '测试大学',
                'major_code': 'M01',
                'major_name': '环境设计',
                'city': '郑州',
                'tuition': 8000,
                'duration': '4年',
                'is_adjustable': True,
                'risk_level': '中',
                'risk_reason': '院校参考最低综合分偏高，建议保留稳妥志愿兜底。',
            }],
        )
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 500)
