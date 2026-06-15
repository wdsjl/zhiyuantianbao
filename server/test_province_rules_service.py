import unittest

from province_rules_service import (
    LEGACY_DEFAULT_VOLUNTEER_COUNT,
    ensure_province_rules_seeded,
    normalize_volunteer_override,
    resolve_volunteer_slots,
    _normalize_province,
    _score_rule_match,
)


class ProvinceRulesServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_province_rules_seeded()

    def test_normalize_province(self):
        self.assertEqual(_normalize_province('河南省'), '河南')
        self.assertEqual(_normalize_province('北京'), '北京')

    def test_batch_match_score(self):
        self.assertEqual(_score_rule_match('本科批', '本科批'), 100)
        self.assertGreater(_score_rule_match('普通类一段', '普通类一段'), 0)
        self.assertGreater(_score_rule_match('专科批', '高职专科批'), 0)

    def test_henan_undergraduate_slots(self):
        result = resolve_volunteer_slots('河南', '本科批')
        self.assertEqual(result['total_slots'], 48)
        self.assertEqual(result['rule']['volunteer_mode'], '院校专业组')

    def test_zhejiang_segment_slots(self):
        result = resolve_volunteer_slots('浙江', '普通类一段')
        self.assertEqual(result['total_slots'], 80)

    def test_shandong_undergraduate_alias(self):
        result = resolve_volunteer_slots('山东', '本科批')
        self.assertEqual(result['total_slots'], 96)

    def test_liaoning_max_slots(self):
        result = resolve_volunteer_slots('辽宁', '本科批')
        self.assertEqual(result['total_slots'], 112)

    def test_override_count(self):
        result = resolve_volunteer_slots('河南', '本科批', override_count=12)
        self.assertEqual(result['total_slots'], 12)
        self.assertEqual(result['source'], 'override')

    def test_legacy_default_nine_uses_province_rule(self):
        self.assertEqual(LEGACY_DEFAULT_VOLUNTEER_COUNT, 9)
        self.assertIsNone(normalize_volunteer_override(0))
        self.assertIsNone(normalize_volunteer_override(9))
        result = resolve_volunteer_slots('河南', '本科批', override_count=9)
        self.assertEqual(result['total_slots'], 48)
        self.assertEqual(result['source'], 'province_rule')


if __name__ == '__main__':
    unittest.main()
