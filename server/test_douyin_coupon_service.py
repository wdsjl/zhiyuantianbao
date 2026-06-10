import unittest

from douyin_coupon_service import (
    ensure_douyin_coupon_tables,
    issue_coupons_from_spi,
    redeem_coupon,
    resolve_plan_code,
    _normalize_coupon_code,
)
from douyin_service import get_douyin_status


class DouyinCouponServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_douyin_coupon_tables()

    def test_resolve_plan_by_third_sku(self):
        plan = resolve_plan_code({'sku_name': '智愿填报金卡'}, third_sku_id='standard')
        self.assertEqual(plan, 'standard')

    def test_resolve_plan_by_name_hint(self):
        plan = resolve_plan_code({'sku_name': '黄金卡会员'})
        self.assertEqual(plan, 'standard')

    def test_issue_and_redeem_coupon(self):
        order_id = 'DYTESTORDER001'
        issued = issue_coupons_from_spi({
            'order_id': order_id,
            'copies': 1,
            'sku': {
                'sku_id': 'sku-gold',
                'sku_name': '黄金卡',
                'third_sku_id': 'standard',
            },
        })
        self.assertEqual(issued['data']['result'], 1)
        code = issued['data']['vouchers'][0]['entrance']['certificate_nos'][0]
        _normalize_coupon_code(code)

        # 无真实用户时仅验证发券幂等
        issued_again = issue_coupons_from_spi({
            'order_id': order_id,
            'copies': 1,
            'sku': {'sku_name': '黄金卡', 'third_sku_id': 'standard'},
        })
        self.assertEqual(
            issued_again['data']['vouchers'][0]['entrance']['certificate_nos'][0],
            code,
        )


class DouyinServiceConfigTest(unittest.TestCase):
    def test_status_without_secret(self):
        import os
        old = os.environ.pop('DOUYIN_APP_SECRET', None)
        try:
            status = get_douyin_status()
            self.assertIn('DOUYIN_APP_SECRET', status['missing'])
        finally:
            if old:
                os.environ['DOUYIN_APP_SECRET'] = old


if __name__ == '__main__':
    unittest.main()
