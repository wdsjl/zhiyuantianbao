import unittest
from datetime import datetime

from membership_service import DEFAULT_PLAN_PERMISSIONS, get_season_expires_at, ensure_membership_tables


class MembershipPricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_membership_tables()

    def test_season_expires_before_september(self) -> None:
        expires = get_season_expires_at(datetime(2026, 6, 5, 10, 0, 0))
        self.assertEqual(expires, '2026-09-30 23:59:59')

    def test_season_expires_after_september(self) -> None:
        expires = get_season_expires_at(datetime(2026, 10, 1, 10, 0, 0))
        self.assertEqual(expires, '2027-09-30 23:59:59')

    def test_trial_has_no_smart_or_pdf_permissions(self) -> None:
        trial = DEFAULT_PLAN_PERMISSIONS['trial']
        self.assertNotIn('smart_recommend', trial)
        self.assertNotIn('pdf_export', trial)
        self.assertNotIn('personality_deep', trial)

    def test_premium_has_unlimited_permissions(self) -> None:
        for limit in DEFAULT_PLAN_PERMISSIONS['premium'].values():
            self.assertEqual(limit, -1)


if __name__ == '__main__':
    unittest.main()
