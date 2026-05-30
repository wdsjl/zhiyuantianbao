import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'zhiyuan.db'
SCHEMA_PATH = BASE_DIR / 'schema.sql'
SEED_PATH = BASE_DIR / 'seed.sql'


def run_script(connection, path):
    sql = path.read_text(encoding='utf-8')
    connection.executescript(sql)


def main():
    connection = sqlite3.connect(DB_PATH)
    try:
      connection.execute('PRAGMA foreign_keys = ON;')
      run_script(connection, SCHEMA_PATH)
      run_script(connection, SEED_PATH)
      connection.commit()
    finally:
      connection.close()

    print(f'Database initialized: {DB_PATH}')


if __name__ == '__main__':
    main()
