"""河南专家版表格导入映射测试。"""
from __future__ import annotations

import io
import unittest
import zipfile

from openpyxl import Workbook

from import_service import (
    _extract_hyperlinks_by_row,
    find_header_row_index,
    normalize_expert_profile_row,
    normalize_row,
    parse_expert_school_profiles_only,
    resolve_import_header,
    sync_school_profiles_from_expert_rows,
)


class ExpertImportTests(unittest.TestCase):
    def test_resolve_expert_headers(self) -> None:
        self.assertEqual(resolve_import_header('生源地'), 'province')
        self.assertEqual(resolve_import_header('专业全称'), 'major_name')
        self.assertEqual(resolve_import_header('2025招生章程'), 'regulation_url')
        self.assertEqual(resolve_import_header('院校保研率'), 'postgraduate_rate')
        self.assertEqual(resolve_import_header('专业组最低分'), 'min_score')

    def test_find_header_row_index(self) -> None:
        rows = [
            ('河南高考志愿填报大数据（专家版）', '', ''),
            ('2025年招生计划', '', ''),
            ('年份', '生源地', '批次', '院校代码', '院校名称', '专业代码', '专业全称', '保研率', '2025招生章程'),
        ]
        self.assertEqual(find_header_row_index(rows), 2)

    def test_normalize_expert_row(self) -> None:
        row = normalize_row({
            '年份': 2025,
            '生源地': '河南',
            '批次': '本科批',
            '院校代码': '1115',
            '院校名称': '清华大学',
            '专业代码': '31',
            '专业全称': '理科试验班类',
            '保研率': '61.2',
            '2025招生章程': 'https://gaokao.chsi.com.cn/zsgs/zhangcheng/listZszc--schId-1.dhtml',
            '专业组最低分': 692,
            '专业组最低位次': 339,
        })
        self.assertEqual(row['province'], '河南')
        self.assertEqual(row['major_name'], '理科试验班类')
        self.assertEqual(row['postgraduate_rate'], '61.2%')
        self.assertEqual(row['regulation_year'], 2026)
        self.assertEqual(row['min_score'], 692)
        self.assertEqual(row['min_rank'], 339)

    def test_sync_school_profiles_dedup_by_school(self) -> None:
        result = sync_school_profiles_from_expert_rows('demo.xlsx', [
            {
                'school_code': '1115',
                'school_name': '清华大学',
                'postgraduate_rate': '61.2%',
                'regulation_url': 'https://gaokao.chsi.com.cn/zsgs/zhangcheng/listZszc--schId-1.dhtml',
                'regulation_year': 2026,
            },
            {
                'school_code': '1115',
                'school_name': '清华大学',
                'major_name': '电子信息类',
            },
        ])
        self.assertEqual(result['total_count'], 1)
        self.assertEqual(result['schools_with_regulation'], 1)

    def test_normalize_expert_profile_row(self) -> None:
        row = normalize_expert_profile_row({
            '院校代码': '1115',
            '院校名称': '清华大学',
            '保研率': '61.2',
            '2025招生章程': 'https://gaokao.chsi.com.cn/zsgs/zhangcheng/listZszc--schId-1.dhtml',
            '专业全称': '应忽略',
        })
        self.assertEqual(row['school_code'], '1115')
        self.assertEqual(row['postgraduate_rate'], '61.2%')
        self.assertEqual(row['regulation_year'], 2026)
        self.assertNotIn('major_name', row)

    def test_parse_expert_school_profiles_only_dedup(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['标题行'])
        sheet.append([
            '年份', '生源地', '批次', '院校代码', '院校名称', '专业代码', '专业全称', '保研率', '2025招生章程',
        ])
        sheet.append([
            2025, '河南', '本科批', '1115', '清华大学', '01', '电子信息类', '61.2',
            'https://gaokao.chsi.com.cn/zsgs/zhangcheng/listZszc--schId-1.dhtml',
        ])
        sheet.append([
            2025, '河南', '本科批', '1115', '清华大学', '02', '计算机类', '61.2', '',
        ])
        buffer = io.BytesIO()
        workbook.save(buffer)
        rows = parse_expert_school_profiles_only(buffer.getvalue())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['school_name'], '清华大学')
        self.assertEqual(rows[0]['postgraduate_rate'], '61.2%')

    def test_extract_hyperlinks_by_row(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['院校名称', '2025招生章程'])
        sheet['B2'].hyperlink = 'https://gaokao.chsi.com.cn/demo'
        sheet['B2'].value = '章程'
        buffer = io.BytesIO()
        workbook.save(buffer)
        content = buffer.getvalue()
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            sheet_path = next(name for name in zf.namelist() if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'))
        links = _extract_hyperlinks_by_row(content, sheet_path)
        self.assertEqual(links.get(2), 'https://gaokao.chsi.com.cn/demo')


if __name__ == '__main__':
    unittest.main()
