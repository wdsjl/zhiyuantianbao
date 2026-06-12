import unittest

from bean_service import adjust_beans, consume_report_beans, ensure_bean_tables, get_bean_balance
from db import get_connection
from user_flags_service import ensure_user_flags, is_super_tester, set_super_tester


class SuperTesterTests(unittest.TestCase):
    TEST_USER_ID = 99901

    def setUp(self) -> None:
        ensure_user_flags()
        ensure_bean_tables()
        with get_connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO users (user_id, openid, role, name) VALUES (?, 'test-super-99901', 'student', '测试用户')",
                [self.TEST_USER_ID],
            )
            connection.execute(
                'INSERT OR IGNORE INTO user_bean_accounts (user_id, balance) VALUES (?, 0)',
                [self.TEST_USER_ID],
            )
            connection.execute(
                'UPDATE user_bean_accounts SET balance = 100 WHERE user_id = ?',
                [self.TEST_USER_ID],
            )
            connection.commit()
        set_super_tester(self.TEST_USER_ID, False)

    def test_super_tester_skips_bean_consume(self) -> None:
        set_super_tester(self.TEST_USER_ID, True)
        self.assertTrue(is_super_tester(self.TEST_USER_ID))
        before = get_bean_balance(self.TEST_USER_ID)['balance']
        result = consume_report_beans(self.TEST_USER_ID, '测试报告')
        after = get_bean_balance(self.TEST_USER_ID)['balance']
        self.assertEqual(result.get('consumed'), 0)
        self.assertTrue(result.get('super_tester'))
        self.assertEqual(before, after)

    def test_adjust_beans(self) -> None:
        set_super_tester(99901, False)
        result = adjust_beans(99901, 500, 'test')
        self.assertEqual(result['balance'], 600)


if __name__ == '__main__':
    unittest.main()
