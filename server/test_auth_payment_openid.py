"""支付前 openid 升级测试。"""

import unittest

from auth_service import is_temp_openid, resolve_payment_openid
from db import get_connection


class AuthPaymentOpenidTests(unittest.TestCase):
    def test_is_temp_openid(self) -> None:
        self.assertTrue(is_temp_openid('local_13800000000'))
        self.assertTrue(is_temp_openid('dev_123'))
        self.assertFalse(is_temp_openid('oAbc1234567890'))

    def test_resolve_payment_openid_upgrades_local_openid(self) -> None:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (openid, phone, role, name) VALUES ('local_pay_test', '13900001111', 'student', '支付测试')"
            )
            user_id = cursor.lastrowid
            connection.commit()

        try:
            resolved = resolve_payment_openid(user_id, {
                'openid': 'oPayUpgradeTestOpenid001',
                'unionid': 'union_test_001',
                'session_key': 'sess',
            })
            self.assertEqual(resolved, 'oPayUpgradeTestOpenid001')
            with get_connection() as connection:
                row = connection.execute(
                    'SELECT openid, unionid FROM users WHERE user_id = ?',
                    [user_id],
                ).fetchone()
            self.assertEqual(row[0], 'oPayUpgradeTestOpenid001')
            self.assertEqual(row[1], 'union_test_001')
        finally:
            with get_connection() as connection:
                connection.execute('DELETE FROM users WHERE user_id = ?', [user_id])
                connection.commit()

    def test_resolve_payment_openid_rejects_conflict(self) -> None:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO users (openid, phone, role, name) VALUES ('oExistingWechatUser', '13900002222', 'student', '已绑定')"
            )
            cursor = connection.execute(
                "INSERT INTO users (openid, phone, role, name) VALUES ('local_conflict_test', '13900003333', 'student', '冲突测试')"
            )
            user_id = cursor.lastrowid
            connection.commit()

        try:
            with self.assertRaises(ValueError) as ctx:
                resolve_payment_openid(user_id, {
                    'openid': 'oExistingWechatUser',
                    'session_key': 'sess',
                })
            self.assertIn('其他账号', str(ctx.exception))
        finally:
            with get_connection() as connection:
                connection.execute('DELETE FROM users WHERE user_id = ?', [user_id])
                connection.execute("DELETE FROM users WHERE openid = 'oExistingWechatUser'")
                connection.commit()
