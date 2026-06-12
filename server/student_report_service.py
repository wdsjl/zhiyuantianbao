"""学生个性化 AI 填报报告：汇总分数、霍兰德测评、个人需求后生成。"""

from __future__ import annotations

import json
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts
from personality_service import build_personality_ai_context, get_latest_assessment
from province_rules_service import resolve_volunteer_slots


def ensure_student_report_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS student_ai_reports (
              report_id INTEGER PRIMARY KEY AUTOINCREMENT,
              student_id INTEGER,
              user_id INTEGER,
              preferences_json TEXT,
              report_content TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
              FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
            '''
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_student_ai_reports_student ON student_ai_reports(student_id, created_at DESC)'
        )
        connection.commit()


def save_student_report(
    student_id: int | None,
    user_id: int | None,
    preferences: dict[str, Any],
    report_content: str,
) -> int:
    ensure_student_report_tables()
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO student_ai_reports (student_id, user_id, preferences_json, report_content)
            VALUES (?, ?, ?, ?)
            ''',
            [student_id, user_id, json.dumps(preferences, ensure_ascii=False), report_content]
        )
        connection.commit()
        return cursor.lastrowid


def get_latest_student_report(student_id: int) -> dict[str, Any] | None:
    ensure_student_report_tables()
    with get_connection() as connection:
        row = connection.execute(
            '''
            SELECT * FROM student_ai_reports
            WHERE student_id = ?
            ORDER BY report_id DESC
            LIMIT 1
            ''',
            [student_id]
        ).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        try:
            data['preferences'] = json.loads(data.pop('preferences_json') or '{}')
        except json.JSONDecodeError:
            data['preferences'] = {}
        return data


def _join_list(value: Any) -> str:
    if not value:
        return '未填写'
    if isinstance(value, list):
        return '、'.join(str(item) for item in value if item)
    return str(value)


def build_student_profile_block(profile: dict[str, Any]) -> str:
    return '\n'.join([
        f"姓名：{profile.get('name') or profile.get('studentName') or '未填写'}",
        f"省份：{profile.get('province', '')}",
        f"城市：{profile.get('city', '')}",
        f"高中：{profile.get('school') or profile.get('school_name', '')}",
        f"年级班级：{profile.get('grade', '')} {profile.get('className') or profile.get('class_name', '')}",
        f"选科组合：{profile.get('subjectCombination') or profile.get('subject_combination', '')}",
        f"高考分数：{profile.get('score', '')}",
        f"全省位次：{profile.get('rank', '')}",
        f"目标批次：{profile.get('targetBatch') or profile.get('target_batch', '')}",
        f"考试年份：{profile.get('examYear') or profile.get('exam_year', '')}",
    ])


def build_preferences_block(preferences: dict[str, Any]) -> str:
    return '\n'.join([
        f"意向城市：{_join_list(preferences.get('preferredCities'))}",
        f"意向专业大类：{_join_list(preferences.get('preferredMajorTypes'))}",
        f"感兴趣专业：{_join_list(preferences.get('preferredMajors'))}",
        f"不想考虑的方向：{_join_list(preferences.get('avoidDirections'))}",
        f"院校层次偏好：{preferences.get('schoolLevelPreference') or '未填写'}",
        f"公办/民办偏好：{preferences.get('schoolNaturePreference') or '未填写'}",
        f"学费预算：{preferences.get('tuitionBudget') or '未填写'}",
        f"职业目标：{preferences.get('careerGoal') or '未填写'}",
        f"是否接受调剂：{preferences.get('acceptAdjustment', '未填写')}",
        f"其他补充：{preferences.get('otherNotes') or '无'}",
    ])


def student_row_to_profile(student: dict[str, Any]) -> dict[str, Any]:
    return {
        'name': student.get('name'),
        'studentName': student.get('name'),
        'province': student.get('province'),
        'city': student.get('city'),
        'school': student.get('school_name'),
        'school_name': student.get('school_name'),
        'grade': student.get('grade'),
        'className': student.get('class_name'),
        'class_name': student.get('class_name'),
        'subjectCombination': student.get('subject_combination'),
        'subject_combination': student.get('subject_combination'),
        'score': student.get('score'),
        'rank': student.get('rank'),
        'targetBatch': student.get('target_batch'),
        'target_batch': student.get('target_batch'),
        'examYear': student.get('exam_year'),
        'exam_year': student.get('exam_year'),
    }


def assessment_to_personality(assessment: dict[str, Any]) -> dict[str, Any]:
    report = assessment.get('report') or {}
    personality = dict(report)
    if assessment.get('ai_career_report'):
        personality['aiCareerReport'] = assessment['ai_career_report']
    if assessment.get('holland_code') and not personality.get('code'):
        personality['code'] = assessment['holland_code']
    return personality


def _load_student_row(student_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        return row_to_dict(
            connection.execute('SELECT * FROM students WHERE student_id = ?', [student_id]).fetchone()
        )


def build_volunteer_summary_from_db(student_id: int, limit: int = 48) -> str:
    with get_connection() as connection:
        draft = row_to_dict(
            connection.execute(
                '''
                SELECT * FROM volunteer_drafts
                WHERE student_id = ?
                ORDER BY updated_at DESC, draft_id DESC
                LIMIT 1
                ''',
                [student_id],
            ).fetchone()
        )
        if not draft:
            return ''
        items = rows_to_dicts(
            connection.execute(
                '''
                SELECT * FROM volunteer_draft_items
                WHERE draft_id = ?
                ORDER BY sort_order ASC
                ''',
                [draft['draft_id']],
            ).fetchall()
        )
    if not items:
        return ''
    lines = [
        f'{index + 1}. {item.get("gradient_type", "")} {item.get("school_name", "")} - {item.get("major_name", "")}'
        for index, item in enumerate(items[:limit])
    ]
    risk_level = draft.get('risk_level') or ''
    header = f'方案名称：{draft.get("draft_name") or "志愿草稿"}；风险等级：{risk_level}；共 {len(items)} 个志愿单位'
    if len(items) > limit:
        header += f'（摘要展示前 {limit} 条）'
    return f'{header}\n' + '\n'.join(lines)


def build_admission_data_context(province: str, batch: str, rank: int | None = None) -> str:
    province = (province or '').strip()
    batch = (batch or '').strip()
    if not province:
        return '暂无本省历年录取数据库记录。'
    with get_connection() as connection:
        stats = row_to_dict(
            connection.execute(
                '''
                SELECT COUNT(*) AS record_count,
                       COUNT(DISTINCT school_id) AS school_count,
                       COUNT(DISTINCT major_id) AS major_count,
                       MIN(year) AS min_year,
                       MAX(year) AS max_year
                FROM admission_records
                WHERE province = ? AND batch = ?
                ''',
                [province, batch],
            ).fetchone()
        )
        sample_sql = '''
            SELECT ar.min_rank, ar.min_score, s.school_name, m.major_name
            FROM admission_records ar
            JOIN schools s ON s.school_id = ar.school_id
            JOIN majors m ON m.major_id = ar.major_id
            WHERE ar.province = ? AND ar.batch = ?
        '''
        params: list[Any] = [province, batch]
        if rank and int(rank) > 0:
            sample_sql += ' AND ar.min_rank IS NOT NULL ORDER BY ABS(ar.min_rank - ?) ASC LIMIT 8'
            params.append(int(rank))
        else:
            sample_sql += ' ORDER BY ar.year DESC, ar.min_rank ASC LIMIT 8'
        samples = rows_to_dicts(connection.execute(sample_sql, params).fetchall())
    if not stats or not int(stats.get('record_count') or 0):
        return f'数据库中暂无 {province} {batch} 的历年录取记录，报告将主要依据测评与分数位次。'
    lines = [
        f'本省批次：{province} {batch}',
        f'数据库录取记录：{stats.get("record_count")} 条，覆盖院校 {stats.get("school_count")} 所、专业 {stats.get("major_count")} 个',
        f'数据年份范围：{stats.get("min_year")} - {stats.get("max_year")}',
    ]
    if rank:
        lines.append(f'学生位次：{rank}（以下展示数据库中与该位次接近的样例院校专业，供报告引用）')
    if samples:
        lines.append('位次邻近样例：')
        lines.extend(
            f"- {row.get('school_name')} / {row.get('major_name')}：近年位次约 {row.get('min_rank')}，分数约 {row.get('min_score')}"
            for row in samples
        )
    return '\n'.join(lines)


def build_province_rule_context(province: str, batch: str) -> str:
    resolved = resolve_volunteer_slots(province, batch)
    rule = resolved['rule']
    if not rule:
        return ''
    return '\n'.join([
        f"省份：{rule.get('province') or province}",
        f"批次：{rule.get('batch') or batch}",
        f"志愿模式：{rule.get('volunteer_mode') or ''}",
        f"志愿单位数：{resolved.get('total_slots') or rule.get('school_count') or ''}",
        f"每组专业数：{rule.get('major_count_per_school') or ''}",
        f"规则说明：{rule.get('rule_description') or ''}",
    ])


def merge_report_inputs_from_db(
    student_id: int | None,
    profile: dict[str, Any],
    personality: dict[str, Any],
    preferences: dict[str, Any],
    volunteer_summary: str | None,
) -> dict[str, Any]:
    merged_profile = dict(profile or {})
    merged_personality = dict(personality or {})
    merged_preferences = dict(preferences or {})
    merged_summary = (volunteer_summary or '').strip()
    province_rule_context = ''
    admission_data_context = ''

    if student_id:
        student_row = _load_student_row(int(student_id))
        if student_row:
            db_profile = student_row_to_profile(student_row)
            merged_profile = {**db_profile, **{k: v for k, v in merged_profile.items() if v not in (None, '', [])}}

        assessment = get_latest_assessment(int(student_id))
        if assessment:
            db_personality = assessment_to_personality(assessment)
            merged_personality = {**db_personality, **{k: v for k, v in merged_personality.items() if v not in (None, '', [], {})}}

        latest_report = get_latest_student_report(int(student_id))
        if latest_report and latest_report.get('preferences') and not merged_preferences:
            merged_preferences = latest_report['preferences']

        db_summary = build_volunteer_summary_from_db(int(student_id))
        if db_summary:
            merged_summary = db_summary
        elif not merged_summary:
            merged_summary = ''

    province = str(merged_profile.get('province') or merged_profile.get('province_name') or '').strip()
    batch = str(merged_profile.get('targetBatch') or merged_profile.get('target_batch') or '').strip()
    rank_value = merged_profile.get('rank')
    try:
        rank_int = int(rank_value) if rank_value not in (None, '') else None
    except (TypeError, ValueError):
        rank_int = None

    if province:
        province_rule_context = build_province_rule_context(province, batch)
        admission_data_context = build_admission_data_context(province, batch, rank_int)

    return {
        'profile': merged_profile,
        'personality': merged_personality,
        'preferences': merged_preferences,
        'volunteer_summary': merged_summary,
        'province_rule_context': province_rule_context,
        'admission_data_context': admission_data_context,
    }


def build_student_report_prompt(
    profile: dict[str, Any],
    personality: dict[str, Any],
    preferences: dict[str, Any],
    volunteer_summary: str | None = None,
    province_rule_context: str | None = None,
    admission_data_context: str | None = None,
) -> str:
    personality_block = build_personality_ai_context(personality)
    volunteer_block = volunteer_summary or '尚未生成志愿方案，请主要依据分数位次与兴趣测评给出策略。'
    student_name = (profile.get('name') or profile.get('studentName') or '同学').strip() or '同学'
    greeting = (
        f'{student_name}同学、{student_name}同学家长，您好：'
        if student_name != '同学' else
        '尊敬的同学、同学家长，您好：'
    )
    return f'''
请作为专业、谨慎的高考志愿填报顾问，基于以下学生完整信息，生成一份「个性化高考志愿填报报告」。

写作要求：
0. 报告正文第一段必须是：「{greeting}」，然后空一行再写后续内容。
0.1 禁止使用「好的」「当然」「没问题」等口语作为开头。
1. 不承诺录取，不使用“保证”“一定录取”等表述。
2. 报告必须体现该学生的个体差异，不要写成通用模板。
3. 结构请使用以下标题（可适度展开）：
   ## 一、学生画像与成绩定位
   ## 二、霍兰德兴趣与专业适配分析
   ## 三、结合个人需求的院校与专业方向建议
   ## 四、冲稳保志愿策略建议
   ## 五、需要重点关注的风险与误区
   ## 六、接下来 7 天的行动建议
4. 语言面向学生和家长，清晰、务实，总字数 900～1200 字。
5. 必须强调：最终以各省教育考试院、高校招生章程和正式填报系统为准。

【学生档案】
{build_student_profile_block(profile)}

【霍兰德职业兴趣测评】
{personality_block}

【学生个人需求与偏好】
{build_preferences_block(preferences)}

【当前志愿方案概况】
{volunteer_block}

【本省志愿填报规则（系统数据库）】
{province_rule_context or '未匹配到省份规则，请结合学生档案中的省份与批次判断。'}

【本省历年录取数据库摘要（系统数据库）】
{admission_data_context or '暂无数据库录取记录摘要。'}
'''
