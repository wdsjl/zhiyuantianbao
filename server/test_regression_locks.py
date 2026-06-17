"""回归锁测试 — 修改会员/志愿/院校/虚拟支付相关代码后必须全部通过。"""

import unittest
import unittest.mock
from datetime import datetime

from membership_service import (
    DEFAULT_PLAN_PERMISSIONS,
    check_permission,
    ensure_membership_tables,
    get_season_expires_at,
    grant_membership,
    seed_membership_defaults,
)
from province_rules_service import (
    ensure_province_rules_seeded,
    normalize_volunteer_override,
    resolve_volunteer_slots,
)
from regression_locks import (
    HENAN_BENKE_VOLUNTEER_SLOTS,
    LEGACY_DEMO_VOLUNTEER_COUNT,
    PDF_EXPORT_PERMISSION,
    PREMIUM_PLAN_CODE,
    VIRTUAL_PAY_WX_ORDER_PREFIX,
    check_locked_source_files,
)
from wechat_virtual_pay_service import _split_virtual_pay_ids


class RegressionLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_membership_tables()
        ensure_province_rules_seeded()

    def test_locked_source_files(self) -> None:
        errors = check_locked_source_files()
        self.assertEqual(errors, [], '回归契约被破坏:\n' + '\n'.join(errors))

    def test_henan_benke_volunteer_slots_is_48(self) -> None:
        resolved = resolve_volunteer_slots('河南', '本科批')
        self.assertEqual(resolved['total_slots'], HENAN_BENKE_VOLUNTEER_SLOTS)
        self.assertTrue((resolved.get('rule') or {}).get('matched'))

    def test_legacy_volunteer_count_9_means_use_province_rules(self) -> None:
        self.assertIsNone(normalize_volunteer_override(0))
        self.assertIsNone(normalize_volunteer_override(LEGACY_DEMO_VOLUNTEER_COUNT))
        self.assertEqual(normalize_volunteer_override(12), 12)

    def test_premium_pdf_export_unlimited(self) -> None:
        perms = DEFAULT_PLAN_PERMISSIONS[PREMIUM_PLAN_CODE]
        self.assertIn(PDF_EXPORT_PERMISSION, perms)
        self.assertEqual(perms[PDF_EXPORT_PERMISSION], -1)

    def test_premium_user_pdf_export_allowed_in_db(self) -> None:
        seed_membership_defaults()
        with unittest.mock.patch('membership_service.get_active_membership') as mock_active:
            mock_active.return_value = {
                'plan_code': PREMIUM_PLAN_CODE,
                'user_membership_id': 1,
                'expires_at': get_season_expires_at(datetime(2026, 6, 5)),
            }
            result = check_permission(95, PDF_EXPORT_PERMISSION)
        self.assertTrue(result['allowed'], result)

    def test_virtual_pay_notify_uses_vpo_not_wxpay_txn(self) -> None:
        virtual_id, txn_id = _split_virtual_pay_ids({
            'wx_order_id': 'VPO260611202131003006728',
            'wxpay_order_id': '700002631032751',
        })
        self.assertTrue(virtual_id.startswith(VIRTUAL_PAY_WX_ORDER_PREFIX))
        self.assertTrue(txn_id.startswith('70000'))

    def test_stale_db_henan_45_upgrades_to_48(self) -> None:
        from db import get_connection
        ensure_province_rules_seeded()
        with get_connection() as connection:
            connection.execute(
                '''
                UPDATE province_rules
                SET school_count = 45, rule_description = 'stale test row'
                WHERE province = '河南' AND batch = '本科批'
                '''
            )
            connection.commit()
        resolved = resolve_volunteer_slots('河南', '本科批')
        self.assertEqual(resolved['total_slots'], HENAN_BENKE_VOLUNTEER_SLOTS)
        self.assertTrue((resolved.get('rule') or {}).get('catalog_enforced'))


if __name__ == '__main__':
    unittest.main()
