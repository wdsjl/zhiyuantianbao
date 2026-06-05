import csv
import io
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts

PAGE_SIZE = 50


def paginate(sql_base: str, params: list[Any], page: int, page_size: int = PAGE_SIZE) -> tuple[list[dict[str, Any]], int]:
    page = max(page, 1)
    offset = (page - 1) * page_size
    count_sql = f'SELECT COUNT(*) FROM ({sql_base})'
    data_sql = f'{sql_base} LIMIT ? OFFSET ?'
    with get_connection() as connection:
        total = connection.execute(count_sql, params).fetchone()[0]
        rows = rows_to_dicts(connection.execute(data_sql, params + [page_size, offset]).fetchall())
    return rows, total


def search_schools(keyword: str = '', page: int = 1) -> tuple[list[dict[str, Any]], int]:
    sql = 'SELECT * FROM schools WHERE 1=1'
    params: list[Any] = []
    if keyword:
        sql += ' AND (school_name LIKE ? OR school_code LIKE ? OR city LIKE ? OR province LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY school_id DESC'
    return paginate(sql, params, page)


def get_school(school_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM schools WHERE school_id = ?', [school_id]).fetchone())


def save_school(data: dict[str, Any], school_id: int | None = None) -> int:
    fields = [
        'school_code', 'school_name', 'province', 'city', 'school_type', 'education_level',
        'is_985', 'is_211', 'is_double_first_class', 'is_public', 'authority', 'website'
    ]
    values = [
        data['school_code'], data['school_name'], data.get('province'), data.get('city'),
        data.get('school_type'), data.get('education_level'),
        1 if data.get('is_985') else 0, 1 if data.get('is_211') else 0,
        1 if data.get('is_double_first_class') else 0, 1 if data.get('is_public', True) else 0,
        data.get('authority'), data.get('website')
    ]
    with get_connection() as connection:
        if school_id:
            connection.execute(
                f'''UPDATE schools SET {', '.join(f'{f}=?' for f in fields)}, updated_at=CURRENT_TIMESTAMP WHERE school_id=?''',
                values + [school_id]
            )
            connection.commit()
            return school_id
        cursor = connection.execute(
            f'INSERT INTO schools ({", ".join(fields)}) VALUES ({", ".join(["?"] * len(fields))})',
            values
        )
        connection.commit()
        return cursor.lastrowid


def delete_school(school_id: int) -> None:
    with get_connection() as connection:
        connection.execute('DELETE FROM schools WHERE school_id = ?', [school_id])
        connection.commit()


def search_majors(keyword: str = '', page: int = 1) -> tuple[list[dict[str, Any]], int]:
    sql = 'SELECT * FROM majors WHERE 1=1'
    params: list[Any] = []
    if keyword:
        sql += ' AND (major_name LIKE ? OR major_code LIKE ? OR major_type LIKE ? OR major_category LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY major_id DESC'
    return paginate(sql, params, page)


def get_major(major_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM majors WHERE major_id = ?', [major_id]).fetchone())


def save_major(data: dict[str, Any], major_id: int | None = None) -> int:
    fields = ['major_code', 'major_name', 'major_category', 'major_type', 'degree_type', 'duration']
    values = [
        data['major_code'], data['major_name'], data.get('major_category'),
        data.get('major_type'), data.get('degree_type'), data.get('duration')
    ]
    with get_connection() as connection:
        if major_id:
            connection.execute(
                f'''UPDATE majors SET {', '.join(f'{f}=?' for f in fields)}, updated_at=CURRENT_TIMESTAMP WHERE major_id=?''',
                values + [major_id]
            )
            connection.commit()
            return major_id
        cursor = connection.execute(
            f'INSERT INTO majors ({", ".join(fields)}) VALUES ({", ".join(["?"] * len(fields))})',
            values
        )
        connection.commit()
        return cursor.lastrowid


def delete_major(major_id: int) -> None:
    with get_connection() as connection:
        connection.execute('DELETE FROM majors WHERE major_id = ?', [major_id])
        connection.commit()


def search_admissions(province: str = '', batch: str = '', year: str = '', keyword: str = '', page: int = 1) -> tuple[list[dict[str, Any]], int]:
    sql = '''
    SELECT ar.admission_id, ar.year, ar.province, ar.batch, ar.school_id, ar.major_id,
           s.school_name, s.school_code, m.major_name, m.major_code,
           ar.min_score, ar.min_rank, ar.avg_score, ar.avg_rank, ar.max_score, ar.max_rank, ar.enrollment_count
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if province:
        sql += ' AND ar.province = ?'
        params.append(province)
    if batch:
        sql += ' AND ar.batch = ?'
        params.append(batch)
    if year and year.isdigit():
        sql += ' AND ar.year = ?'
        params.append(int(year))
    if keyword:
        sql += ' AND (s.school_name LIKE ? OR m.major_name LIKE ? OR s.school_code LIKE ? OR m.major_code LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY ar.year DESC, ar.min_rank ASC'
    return paginate(sql, params, page)


def get_admission(admission_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM admission_records WHERE admission_id = ?', [admission_id]).fetchone())


def save_admission(data: dict[str, Any], admission_id: int | None = None) -> int:
    school_id = int(data['school_id'])
    major_id = int(data['major_id'])
    with get_connection() as connection:
        school = row_to_dict(connection.execute('SELECT school_code FROM schools WHERE school_id = ?', [school_id]).fetchone())
        major = row_to_dict(connection.execute('SELECT major_code FROM majors WHERE major_id = ?', [major_id]).fetchone())
        if not school or not major:
            raise ValueError('院校或专业不存在')
        values = [
            int(data['year']), data['province'], data['batch'], school_id, school['school_code'],
            major_id, major['major_code'],
            int(data['min_score']) if data.get('min_score') else None,
            int(data['min_rank']) if data.get('min_rank') else None,
            int(data['avg_score']) if data.get('avg_score') else None,
            int(data['avg_rank']) if data.get('avg_rank') else None,
            int(data['max_score']) if data.get('max_score') else None,
            int(data['max_rank']) if data.get('max_rank') else None,
            int(data['enrollment_count']) if data.get('enrollment_count') else None,
        ]
        if admission_id:
            connection.execute(
                '''UPDATE admission_records SET year=?, province=?, batch=?, school_id=?, school_code=?,
                   major_id=?, major_code=?, min_score=?, min_rank=?, avg_score=?, avg_rank=?,
                   max_score=?, max_rank=?, enrollment_count=?, updated_at=CURRENT_TIMESTAMP WHERE admission_id=?''',
                values + [admission_id]
            )
            connection.commit()
            return admission_id
        cursor = connection.execute(
            '''INSERT INTO admission_records (year, province, batch, school_id, school_code, major_id, major_code,
               min_score, min_rank, avg_score, avg_rank, max_score, max_rank, enrollment_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            values
        )
        connection.commit()
        return cursor.lastrowid


def delete_admission(admission_id: int) -> None:
    with get_connection() as connection:
        connection.execute('DELETE FROM admission_records WHERE admission_id = ?', [admission_id])
        connection.commit()


def search_enrollment_plans(province: str = '', batch: str = '', year: str = '', keyword: str = '', page: int = 1) -> tuple[list[dict[str, Any]], int]:
    sql = '''
    SELECT ep.plan_id, ep.year, ep.province, ep.batch, ep.school_id, ep.major_id,
           s.school_name, s.school_code, ep.major_name, ep.major_code,
           ep.subject_requirement, ep.enrollment_count, ep.tuition, ep.duration, ep.campus, ep.special_notes
    FROM enrollment_plans ep
    JOIN schools s ON s.school_id = ep.school_id
    WHERE 1=1
    '''
    params: list[Any] = []
    if province:
        sql += ' AND ep.province = ?'
        params.append(province)
    if batch:
        sql += ' AND ep.batch = ?'
        params.append(batch)
    if year and year.isdigit():
        sql += ' AND ep.year = ?'
        params.append(int(year))
    if keyword:
        sql += ' AND (s.school_name LIKE ? OR ep.major_name LIKE ? OR s.school_code LIKE ? OR ep.major_code LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY ep.year DESC, ep.plan_id DESC'
    return paginate(sql, params, page)


def get_enrollment_plan(plan_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM enrollment_plans WHERE plan_id = ?', [plan_id]).fetchone())


def save_enrollment_plan(data: dict[str, Any], plan_id: int | None = None) -> int:
    school_id = int(data['school_id'])
    major_id = int(data['major_id'])
    with get_connection() as connection:
        school = row_to_dict(connection.execute('SELECT school_code FROM schools WHERE school_id = ?', [school_id]).fetchone())
        major = row_to_dict(connection.execute('SELECT major_code, major_name FROM majors WHERE major_id = ?', [major_id]).fetchone())
        if not school or not major:
            raise ValueError('院校或专业不存在')
        major_name = data.get('major_name') or major['major_name']
        values = [
            int(data['year']), data['province'], data['batch'], school_id, school['school_code'],
            major_id, major['major_code'], major_name,
            data.get('subject_requirement'),
            int(data['enrollment_count']) if data.get('enrollment_count') else None,
            int(data['tuition']) if data.get('tuition') else None,
            data.get('duration'), data.get('campus'), data.get('special_notes'),
        ]
        if plan_id:
            connection.execute(
                '''UPDATE enrollment_plans SET year=?, province=?, batch=?, school_id=?, school_code=?,
                   major_id=?, major_code=?, major_name=?, subject_requirement=?, enrollment_count=?,
                   tuition=?, duration=?, campus=?, special_notes=?, updated_at=CURRENT_TIMESTAMP WHERE plan_id=?''',
                values + [plan_id]
            )
            connection.commit()
            return plan_id
        cursor = connection.execute(
            '''INSERT INTO enrollment_plans (year, province, batch, school_id, school_code, major_id, major_code,
               major_name, subject_requirement, enrollment_count, tuition, duration, campus, special_notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            values
        )
        connection.commit()
        return cursor.lastrowid


def delete_enrollment_plan(plan_id: int) -> None:
    with get_connection() as connection:
        connection.execute('DELETE FROM enrollment_plans WHERE plan_id = ?', [plan_id])
        connection.commit()


def search_students(keyword: str = '', page: int = 1) -> tuple[list[dict[str, Any]], int]:
    sql = """
    SELECT s.student_id, u.user_id, u.openid, u.phone, u.role, s.name, s.province, s.city,
           s.school_name, s.grade, s.class_name, s.exam_year, s.exam_type, s.subject_combination,
           s.score, s.rank, s.target_batch, s.updated_at
    FROM students s
    JOIN users u ON u.user_id = s.user_id
    WHERE 1=1
    """
    params: list[Any] = []
    if keyword:
        sql += ' AND (s.name LIKE ? OR u.phone LIKE ? OR s.school_name LIKE ? OR s.class_name LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY s.updated_at DESC'
    return paginate(sql, params, page)


def get_student(student_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(connection.execute(
            '''
            SELECT s.*, u.phone, u.role, u.openid
            FROM students s JOIN users u ON u.user_id = s.user_id
            WHERE s.student_id = ?
            ''',
            [student_id]
        ).fetchone())


def save_student(student_id: int, data: dict[str, Any]) -> None:
    with get_connection() as connection:
        student = row_to_dict(connection.execute('SELECT user_id FROM students WHERE student_id = ?', [student_id]).fetchone())
        if not student:
            raise ValueError('学生不存在')
        connection.execute(
            '''UPDATE students SET name=?, province=?, city=?, school_name=?, grade=?, class_name=?,
               exam_year=?, exam_type=?, subject_combination=?, score=?, rank=?, target_batch=?,
               updated_at=CURRENT_TIMESTAMP WHERE student_id=?''',
            [
                data['name'], data['province'], data.get('city'), data.get('school_name'),
                data.get('grade'), data.get('class_name'), int(data['exam_year']),
                data.get('exam_type'), data['subject_combination'],
                int(data['score']), int(data['rank']), data['target_batch'], student_id
            ]
        )
        if data.get('phone') is not None:
            connection.execute(
                'UPDATE users SET phone=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?',
                [data.get('phone'), student['user_id']]
            )
        connection.commit()


def export_students_csv(keyword: str = '') -> str:
    rows, _ = search_students(keyword, page=1)
    # export all matching - re-query without pagination limit
    sql = """
    SELECT s.student_id, u.user_id, u.phone, u.role, s.name, s.province, s.city,
           s.school_name, s.grade, s.class_name, s.exam_year, s.subject_combination,
           s.score, s.rank, s.target_batch, s.updated_at
    FROM students s JOIN users u ON u.user_id = s.user_id WHERE 1=1
    """
    params: list[Any] = []
    if keyword:
        sql += ' AND (s.name LIKE ? OR u.phone LIKE ? OR s.school_name LIKE ? OR s.class_name LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY s.updated_at DESC LIMIT 5000'
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['学生ID', '用户ID', '手机号', '角色', '姓名', '省份', '城市', '学校', '年级', '班级', '年份', '选科', '分数', '位次', '批次', '更新时间'])
    for row in rows:
        writer.writerow([
            row.get('student_id'), row.get('user_id'), row.get('phone'), row.get('role'),
            row.get('name'), row.get('province'), row.get('city'), row.get('school_name'),
            row.get('grade'), row.get('class_name'), row.get('exam_year'),
            row.get('subject_combination'), row.get('score'), row.get('rank'),
            row.get('target_batch'), row.get('updated_at')
        ])
    return output.getvalue()


def search_province_rules(province: str = '', year: str = '', page: int = 1) -> tuple[list[dict[str, Any]], int]:
    sql = 'SELECT * FROM province_rules WHERE 1=1'
    params: list[Any] = []
    if province:
        sql += ' AND province LIKE ?'
        params.append(f'%{province}%')
    if year and year.isdigit():
        sql += ' AND year = ?'
        params.append(int(year))
    sql += ' ORDER BY year DESC, province ASC'
    return paginate(sql, params, page)


def get_province_rule(rule_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM province_rules WHERE rule_id = ?', [rule_id]).fetchone())


def save_province_rule(data: dict[str, Any], rule_id: int | None = None) -> int:
    values = [
        data['province'], int(data['year']), data['batch'], data['volunteer_mode'],
        int(data['school_count']) if data.get('school_count') else None,
        int(data['major_count_per_school']) if data.get('major_count_per_school') else None,
        1 if data.get('is_parallel_volunteer', True) else 0,
        1 if data.get('adjustment_supported', True) else 0,
        data.get('score_priority_rule'), data.get('rule_description'),
    ]
    with get_connection() as connection:
        if rule_id:
            connection.execute(
                '''UPDATE province_rules SET province=?, year=?, batch=?, volunteer_mode=?,
                   school_count=?, major_count_per_school=?, is_parallel_volunteer=?,
                   adjustment_supported=?, score_priority_rule=?, rule_description=?,
                   updated_at=CURRENT_TIMESTAMP WHERE rule_id=?''',
                values + [rule_id]
            )
            connection.commit()
            return rule_id
        cursor = connection.execute(
            '''INSERT INTO province_rules (province, year, batch, volunteer_mode, school_count,
               major_count_per_school, is_parallel_volunteer, adjustment_supported,
               score_priority_rule, rule_description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            values
        )
        connection.commit()
        return cursor.lastrowid


def delete_province_rule(rule_id: int) -> None:
    with get_connection() as connection:
        connection.execute('DELETE FROM province_rules WHERE rule_id = ?', [rule_id])
        connection.commit()


def get_import_log(log_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(connection.execute('SELECT * FROM import_logs WHERE log_id = ?', [log_id]).fetchone())


def list_school_options(keyword: str = '', limit: int = 200) -> list[dict[str, Any]]:
    sql = 'SELECT school_id, school_code, school_name FROM schools WHERE 1=1'
    params: list[Any] = []
    if keyword:
        sql += ' AND (school_name LIKE ? OR school_code LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like])
    sql += ' ORDER BY school_name ASC LIMIT ?'
    params.append(limit)
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())


def list_major_options(keyword: str = '', limit: int = 200) -> list[dict[str, Any]]:
    sql = 'SELECT major_id, major_code, major_name FROM majors WHERE 1=1'
    params: list[Any] = []
    if keyword:
        sql += ' AND (major_name LIKE ? OR major_code LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like])
    sql += ' ORDER BY major_name ASC LIMIT ?'
    params.append(limit)
    with get_connection() as connection:
        return rows_to_dicts(connection.execute(sql, params).fetchall())
