import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'zhiyuan.db'

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

tables = [
    row[0]
    for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
]

print('tables:', ', '.join(tables))
for table in ['schools', 'majors', 'enrollment_plans', 'admission_records', 'province_rules']:
    count = cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table}: {count}')

connection.close()
