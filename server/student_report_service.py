"""学生个性化 AI 填报报告：汇总分数、霍兰德测评、个人需求后生成。"""

from __future__ import annotations

import json
from typing import Any

from db import get_connection, row_to_dict
from personality_service import build_personality_ai_context


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


def build_profile_snapshot(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        'province': profile.get('province') or '',
        'target_batch': profile.get('targetBatch') or profile.get('target_batch') or '',
        'subject_combination': profile.get('subjectCombination') or profile.get('subject_combination') or '',
        'score': profile.get('score'),
        'rank': profile.get('rank'),
    }


def profile_snapshot_matches_student(snapshot: dict[str, Any] | None, student: dict[str, Any] | None) -> bool:
    if not snapshot or not student:
        return False
    return (
        str(snapshot.get('province') or '') == str(student.get('province') or '')
        and str(snapshot.get('target_batch') or '') == str(student.get('target_batch') or '')
        and str(snapshot.get('subject_combination') or '') == str(student.get('subject_combination') or '')
        and str(snapshot.get('score') or '') == str(student.get('score') or '')
        and str(snapshot.get('rank') or '') == str(student.get('rank') or '')
    )


def save_student_report(
    student_id: int | None,
    user_id: int | None,
    preferences: dict[str, Any],
    report_content: str,
    profile: dict[str, Any] | None = None,
) -> int:
    ensure_student_report_tables()
    payload = dict(preferences or {})
    if profile:
        payload['_profile_snapshot'] = build_profile_snapshot(profile)
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO student_ai_reports (student_id, user_id, preferences_json, report_content)
            VALUES (?, ?, ?, ?)
            ''',
            [student_id, user_id, json.dumps(payload, ensure_ascii=False), report_content]
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


def build_student_report_prompt(
    profile: dict[str, Any],
    personality: dict[str, Any],
    preferences: dict[str, Any],
    volunteer_summary: str | None = None,
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
'''
