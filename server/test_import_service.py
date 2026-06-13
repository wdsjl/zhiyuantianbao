import unittest

from import_service import (
    build_major_code,
    detect_header_row_index,
    enrich_import_row,
    normalize_row,
    validate_headers,
)


class ImportServiceTests(unittest.TestCase):
    def test_detect_header_row_skips_title_rows(self):
        rows = [
            ('河南高考志愿填报', None),
            ('2025年招生计划', None),
            ('年份', '省份', '批次', '院校代码', '院校名称', '专业全称', '专业代码'),
            (2025, '河南', '本科批', '4625', '湖北民族大学', '国际经济与贸易', '10'),
        ]
        self.assertEqual(detect_header_row_index(rows), 2)

    def test_validate_headers_accepts_henan_plan_format(self):
        headers = [
            '年份', '省份', '批次', '科类', '院校代码', '院校名称', '院校专业组代码',
            '专业组代码', '专业全称', '专业名称', '专业代码', '选科要求', '计划人数', '学制', '学费', '门类', '专业类',
        ]
        validate_headers(headers)

    def test_normalize_henan_plan_row(self):
        raw = {
            '年份': 2025,
            '省份': '河南',
            '批次': '本科批',
            '科类': '历史',
            '院校代码': '4625',
            '院校名称': '湖北民族大学',
            '院校专业组代码': '4625101',
            '专业组代码': '101',
            '专业组名称': '第101组',
            '专业代码': '10',
            '专业全称': '国际经济与贸易',
            '专业名称': '国际经济与贸易',
            '专业备注': '(数字贸易)',
            '选科要求': '不限',
            '专业层次': '本科',
            '计划人数': 2,
            '学制': 4,
            '学费': 5200,
            '门类': '经济学',
            '专业类': '经济与贸易类',
        }
        row = enrich_import_row(normalize_row(raw))
        self.assertEqual(row['major_code'], '4625101-10')
        self.assertEqual(row['major_name'], '国际经济与贸易')
        self.assertEqual(row['enrollment_count'], 2)
        self.assertEqual(row['tuition'], 5200)
        self.assertEqual(row['duration'], '4年')
        self.assertEqual(row['major_category'], '经济学')
        self.assertEqual(row['major_type'], '经济与贸易类')
        self.assertEqual(row['subject_requirement'], '历史')
        self.assertIn('数字贸易', row['special_notes'])

    def test_build_major_code_fallback(self):
        row = {
            'school_code': '4625',
            'major_group_code': '101',
            'major_code': '10',
        }
        self.assertEqual(build_major_code(row), '462510110')


if __name__ == '__main__':
    unittest.main()
