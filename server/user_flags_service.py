"""用户标记：超级测试账号等。"""

from __future__ import annotations

from db import get_connection, row_to_dict


def ensure_user_flags() -> None:
    with get_connection() as connection:
        columns = {
            row['name']
            for row in connection.execute('PRAGMA table_info(users)').fetchall()
        }
        if 'is_super_tester' not in columns:
            connection.execute(
                'ALTER TABLE users ADD COLUMN is_super_tester INTEGER NOT NULL DEFAULT 0'
            )
        connection.commit()


def is_super_tester(user_id: int | None) -> bool:
    if not user_id:
        return False
    ensure_user_flags()
    with get_connection() as connection:
        row = row_to_dict(
            connection.execute(
                'SELECT is_super_tester FROM users WHERE user_id = ?',
                [int(user_id)],
            ).fetchone()
        )
    return bool(row and int(row.get('is_super_tester') or 0))


def set_super_tester(user_id: int, enabled: bool) -> None:
    ensure_user_flags()
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE users
            SET is_super_tester = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''',
            [1 if enabled else 0, int(user_id)],
        )
        if connection.total_changes == 0:
            raise ValueError('用户不存在')
        connection.commit()
