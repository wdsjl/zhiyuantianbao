import unittest
from unittest.mock import MagicMock, patch

from crawler_service import (
    build_import_row,
    build_special_notes,
    build_subject_requirement,
    extract_campus_from_text,
    normalize_batch_name,
    resolve_enrollment_count,
)
from henan_admission_crawler_service import (
    HENAN_PROVINCE,
    get_henan_admission_summary,
    henan_recent_years,
)


class HenanAdmissionCrawlerTests(unittest.TestCase):
    def test_normalize_batch_maps_henan_legacy_batch(self):
        self.assertEqual(normalize_batch_name('本科一批'), '本科批')

    def test_extract_campus_from_major_name(self):
        major = '经济学（办学地点:南校区;合作方:波兰罗兹大学）'
        self.assertEqual(extract_campus_from_text(major), '南校区')

    def test_resolve_enrollment_count_prefers_actual_admitted(self):
        self.assertEqual(resolve_enrollment_count({'lq_num': '58'}, {'num': 130}), 58)
        self.assertEqual(resolve_enrollment_count(None, {'num': 130}), 130)

    def test_build_import_row_contains_volunteer_fields(self):
        row = build_import_row(
            {'name': '郑州大学', 'p': '河南', 'c': '郑州市', 'level': '本科', 'f211': '1'},
            {'name': '郑州大学', 'zs_code': '10459', 'f211': '1'},
            {
                'spname': '法学',
                'local_batch_name': '本科一批',
                'min': 596,
                'min_section': '2393',
                'average': 599,
                'max': 610,
                'lq_num': '58',
                'zslx_name': '普通类',
                'sg_name': '01组',
                'sp_xuanke': '物理+化学',
            },
            {
                'spname': '法学',
                'num': 60,
                'tuition': '5000',
                'length': '四年',
                'local_batch_name': '本科一批',
            },
            2024,
            '河南',
        )
        self.assertEqual(row['province'], '河南')
        self.assertEqual(row['batch'], '本科批')
        self.assertEqual(row['min_score'], 596)
        self.assertEqual(row['min_rank'], 2393)
        self.assertEqual(row['avg_score'], 599)
        self.assertEqual(row['max_score'], 610)
        self.assertEqual(row['enrollment_count'], 58)
        self.assertEqual(row['tuition'], 5000)
        self.assertEqual(row['duration'], '四年')
        self.assertIn('物理+化学', row['subject_requirement'])
        self.assertIn('招生类型：普通类', row['special_notes'])

    def test_build_subject_requirement_dedupes(self):
        text = build_subject_requirement({'sp_xuanke': '物理'}, {'sp_xuanke': '物理', 'sg_xuanke': '化学'})
        self.assertEqual(text, '物理；化学')

    def test_build_special_notes_includes_group(self):
        text = build_special_notes({'sg_name': '01组', 'zslx_name': '普通类'}, None)
        self.assertIn('专业组：01组', text)
        self.assertIn('招生类型：普通类', text)

    def test_henan_recent_years_returns_three(self):
        with patch('henan_admission_crawler_service.default_recent_years', return_value=[2025, 2024, 2023]):
            self.assertEqual(henan_recent_years(), [2025, 2024, 2023])

    def test_get_henan_admission_summary_structure(self):
        with patch('henan_admission_crawler_service.has_running_crawl', return_value=False), patch(
            'henan_admission_crawler_service.get_province_data_overview',
            return_value=[{'name': HENAN_PROVINCE, 'last_crawl_at': None, 'last_success_at': None}],
        ), patch('henan_admission_crawler_service.get_connection') as mock_conn:
            connection = mock_conn.return_value.__enter__.return_value
            connection.execute.side_effect = [
                MagicMock(fetchall=lambda: []),
                MagicMock(fetchall=lambda: []),
            ]
            summary = get_henan_admission_summary()
        self.assertEqual(summary['province'], '河南')
        self.assertIn('totals', summary)
        self.assertIn('year_stats', summary)


if __name__ == '__main__':
    unittest.main()
