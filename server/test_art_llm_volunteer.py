"""艺术类大模型志愿生成测试。"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from art_llm_volunteer_service import (
    build_art_llm_recommendation,
    collect_art_2025_admissions_via_llm,
    ensure_art_llm_cache_table,
    extract_json_payload,
    generate_art_volunteer_plan_via_llm,
    try_build_art_llm_recommendation,
    try_build_art_sports_llm_recommendation,
)
from db import get_connection


SAMPLE_ADMISSIONS = [
    {'school_name': f'测试艺术大学{i}', 'major_name': f'测试专业{i}', 'min_composite_2025': 520 - i, 'city': '郑州'}
    for i in range(100)
]


def _sample_volunteers(count: int = 64) -> list[dict]:
    volunteers = []
    for index in range(count):
        if index < 16:
            gradient = '冲'
        elif index < 40:
            gradient = '稳'
        else:
            gradient = '保'
        volunteers.append({
            'sort_order': index + 1,
            'gradient_type': gradient,
            'school_name': f'测试艺术大学{index}',
            'major_name': f'测试专业{index}',
            'min_composite_2025': 520 - index,
            'city': '郑州',
        })
    return volunteers


class ArtLlmVolunteerTests(unittest.TestCase):
    def test_extract_json_payload(self) -> None:
        payload = extract_json_payload('```json\n{"admissions":[{"school_name":"A","major_name":"B","min_composite_2025":500}]}\n```')
        self.assertEqual(payload['admissions'][0]['school_name'], 'A')

    @patch('art_llm_volunteer_service.is_llm_available', return_value=True)
    @patch('art_llm_volunteer_service.chat_completion')
    def test_collect_art_admissions_via_llm(self, mock_chat, _mock_available) -> None:
        mock_chat.return_value = json.dumps({'admissions': SAMPLE_ADMISSIONS[:30]}, ensure_ascii=False)
        ensure_art_llm_cache_table()
        with get_connection() as connection:
            connection.execute('DELETE FROM art_llm_admission_cache WHERE province = ? AND batch = ?', ['河南', '艺术本科批'])
            connection.commit()
        rows = collect_art_2025_admissions_via_llm('艺术本科批', 5, '文化50%+专业50%')
        self.assertGreaterEqual(len(rows), 128)
        cached = collect_art_2025_admissions_via_llm('艺术本科批', 5, '文化50%+专业50%')
        self.assertEqual(len(cached), len(rows))
        mock_chat.assert_called_once()

    @patch('art_llm_volunteer_service.chat_completion')
    def test_generate_art_volunteer_plan_via_llm(self, mock_chat) -> None:
        mock_chat.return_value = json.dumps({'volunteers': _sample_volunteers()}, ensure_ascii=False)
        items = generate_art_volunteer_plan_via_llm(
            batch='艺术本科批',
            composite_score=550,
            culture_score=500,
            professional_score=240,
            formula_id=5,
            formula_label='文化50%+专业50%',
            plan_style='balanced',
            admissions=SAMPLE_ADMISSIONS,
        )
        self.assertEqual(len(items), 64)
        self.assertEqual(items[0]['gradient_type'], '冲')
        self.assertEqual(items[0]['data_source'], 'llm_art_2025')
        self.assertIsNotNone(items[0]['ref_min_composite'])

    @patch('art_llm_volunteer_service.is_llm_available', return_value=True)
    @patch('art_llm_volunteer_service.generate_art_volunteer_plan_via_llm')
    @patch('art_llm_volunteer_service.collect_art_2025_admissions_via_llm')
    def test_build_art_llm_recommendation(self, mock_collect, mock_plan, _mock_available) -> None:
        mock_collect.return_value = SAMPLE_ADMISSIONS
        mock_plan.return_value = [
            {
                'sort_order': index + 1,
                'gradient_type': '稳',
                'school_name': f'测试艺术大学{index}',
                'major_name': f'测试专业{index}',
                'ref_min_composite': 500 - index,
                'min_composite_2025': 500 - index,
                'score_diff': 50 - index,
                'school_id': 100000 + index,
                'major_id': 200000 + index,
                'data_source': 'llm_art_2025',
            }
            for index in range(64)
        ]
        result = build_art_llm_recommendation({
            'province': '河南',
            'exam_type': '艺术类',
            'score': 500,
            'professional_score': 240,
            'batch': '艺术本科批',
            'art_sports_formula_id': 5,
            'culture_cutoff': 350,
            'pro_cutoff': 180,
        })
        self.assertTrue(result['art_sports_mode'])
        self.assertEqual(result['generation']['generation_mode'], 'llm')
        self.assertEqual(len(result['items']), 64)
        self.assertEqual(result['strategy']['data_source'], 'llm_art_2025')

    @patch('art_llm_volunteer_service.chat_completion', side_effect=RuntimeError('skip llm plan'))
    def test_expand_art_sports_admissions_reaches_minimum(self, _mock_chat) -> None:
        from henan_art_sports_service import expand_art_sports_admissions, VOLUNTEER_SLOTS
        rows = expand_art_sports_admissions(
            [{'school_name': '测试大学', 'major_name': '美术学', 'min_composite_2025': 500, 'city': '郑州'}],
            category='艺术类',
            batch_level='本科',
            formula_id=5,
            composite_score=520,
            minimum=128,
        )
        self.assertGreaterEqual(len(rows), 128)
        selected = generate_art_volunteer_plan_via_llm(
            batch='艺术本科批',
            composite_score=520,
            culture_score=480,
            professional_score=240,
            formula_id=5,
            formula_label='文化50%+专业50%',
            plan_style='balanced',
            admissions=rows[:5],
            category='艺术类',
        )
        self.assertEqual(len(selected), VOLUNTEER_SLOTS)

    @patch('art_llm_volunteer_service.is_llm_available', return_value=False)
    def test_try_build_returns_error_when_llm_disabled(self, _mock_available) -> None:
        plan, error = try_build_art_sports_llm_recommendation({
            'province': '河南',
            'exam_type': '艺术类',
            'batch': '艺术本科批',
        })
        self.assertIsNone(plan)
        self.assertIn('大模型未启用', error or '')


if __name__ == '__main__':
    unittest.main()
