import unittest

from announcement_pdf_parser_service import (
    map_header_to_field,
    table_rows_to_records,
)


class AnnouncementPdfParserTests(unittest.TestCase):
    def test_map_header_aliases(self):
        self.assertEqual(map_header_to_field('院校代号'), 'school_code')
        self.assertEqual(map_header_to_field('专业名称'), 'major_name')

    def test_table_rows_to_records(self):
        table = [
            ['院校代号', '院校名称', '专业代号', '专业名称', '计划数', '选科要求'],
            ['1046', '郑州大学', '01', '临床医学', '120', '物理+化学'],
            ['1046', '郑州大学', '02', '计算机科学与技术', '80', '物理'],
        ]
        rows = table_rows_to_records(table, year=2026, province='河南', batch='本科批')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['school_name'], '郑州大学')
        self.assertEqual(rows[0]['enrollment_count'], 120)


if __name__ == '__main__':
    unittest.main()
