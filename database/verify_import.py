import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'zhiyuan.db'
connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

print('schools', cursor.execute("SELECT COUNT(*) FROM schools WHERE school_code = '10001'").fetchone()[0])
print('admissions', cursor.execute("SELECT COUNT(*) FROM admission_records ar JOIN schools s ON s.school_id = ar.school_id WHERE s.school_code = '10001'").fetchone()[0])
print('logs', cursor.execute("SELECT COUNT(*) FROM import_logs WHERE import_type = 'admission_records'").fetchone()[0])

connection.close()
