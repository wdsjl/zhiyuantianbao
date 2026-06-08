"""霍兰德职业兴趣测评服务：持久化报告并为 AI 建议提供结构化上下文。"""

from __future__ import annotations

import json
from typing import Any

from db import get_connection, row_to_dict, rows_to_dicts


def ensure_personality_tables() -> None:
    with get_connection() as connection:
        connection.execute(
            '''
            CREATE TABLE IF NOT EXISTS personality_assessments (
              assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
              student_id INTEGER,
              user_id INTEGER,
              holland_code TEXT NOT NULL,
              scores_json TEXT NOT NULL,
              report_json TEXT NOT NULL,
              ai_career_report TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
              FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
            '''
        )
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_personality_student ON personality_assessments(student_id, created_at DESC)'
        )
        connection.commit()


def save_assessment(student_id: int | None, user_id: int | None, report: dict[str, Any]) -> int:
    ensure_personality_tables()
    holland_code = str(report.get('code') or '')
    scores_json = json.dumps(report.get('scores') or {}, ensure_ascii=False)
    report_json = json.dumps(report, ensure_ascii=False)
    with get_connection() as connection:
        cursor = connection.execute(
            '''
            INSERT INTO personality_assessments (student_id, user_id, holland_code, scores_json, report_json)
            VALUES (?, ?, ?, ?, ?)
            ''',
            [student_id, user_id, holland_code, scores_json, report_json]
        )
        connection.commit()
        return cursor.lastrowid


def save_ai_career_report(assessment_id: int, content: str) -> None:
    ensure_personality_tables()
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE personality_assessments
            SET ai_career_report = ?, updated_at = CURRENT_TIMESTAMP
            WHERE assessment_id = ?
            ''',
            [content, assessment_id]
        )
        connection.commit()


def get_latest_assessment(student_id: int) -> dict[str, Any] | None:
    ensure_personality_tables()
    with get_connection() as connection:
        row = connection.execute(
            '''
            SELECT * FROM personality_assessments
            WHERE student_id = ?
            ORDER BY assessment_id DESC
            LIMIT 1
            ''',
            [student_id]
        ).fetchone()
        return _assessment_to_dict(row)


def get_assessment(assessment_id: int) -> dict[str, Any] | None:
    ensure_personality_tables()
    with get_connection() as connection:
        row = connection.execute(
            'SELECT * FROM personality_assessments WHERE assessment_id = ?',
            [assessment_id]
        ).fetchone()
        return _assessment_to_dict(row)


def _assessment_to_dict(row) -> dict[str, Any] | None:
    if not row:
        return None
    data = row_to_dict(row)
    try:
        data['report'] = json.loads(data.pop('report_json') or '{}')
    except json.JSONDecodeError:
        data['report'] = {}
    try:
        data['scores'] = json.loads(data.pop('scores_json') or '{}')
    except json.JSONDecodeError:
        data['scores'] = {}
    return data


def build_personality_ai_context(personality: dict[str, Any]) -> str:
    if not personality:
        return '暂无霍兰德职业兴趣测评数据。'

    ai_context = personality.get('aiContext') or {}
    if ai_context:
        lines = [
            f"霍兰德代码：{ai_context.get('hollandCode') or personality.get('code', '')}",
            f"主-次-辅类型：{ai_context.get('primaryType', '')} / {ai_context.get('secondaryType', '')} / {ai_context.get('tertiaryType', '')}",
            f"测评摘要：{ai_context.get('summary') or personality.get('reportSummary', '')}",
            f"推荐专业大类：{', '.join(ai_context.get('majorTypes') or personality.get('majorTypes') or [])}",
            f"可参考职业：{', '.join(ai_context.get('careers') or personality.get('careers') or [])}",
            f"核心优势：{', '.join(ai_context.get('strengths') or [])}",
            f"填报提醒：{'; '.join(ai_context.get('cautions') or [])}",
        ]
        type_analysis = ai_context.get('typeAnalysis') or []
        if type_analysis:
            lines.append('分型解读：')
            lines.extend([f"- {line}" for line in type_analysis])
        if personality.get('aiCareerReport'):
            lines.append(f"AI 个性化填报报告：\n{personality.get('aiCareerReport')}")
        return '\n'.join([line for line in lines if line and line.strip()])

    primary = personality.get('primaryType') or {}
    if isinstance(primary, dict):
        primary_name = primary.get('name', '')
    else:
        primary_name = str(primary)
    return '\n'.join([
        f"霍兰德代码：{personality.get('code', '')}",
        f"主类型：{primary_name}",
        f"推荐专业大类：{', '.join(personality.get('majorTypes') or [])}",
        f"测评摘要：{personality.get('reportSummary', '')}",
    ])


def build_career_report_prompt(profile: dict[str, Any], personality: dict[str, Any]) -> str:
    context = build_personality_ai_context(personality)
    student_name = (profile.get('name') or profile.get('studentName') or '同学').strip() or '同学'
    greeting = (
        f'{student_name}同学、{student_name}同学家长，您好：'
        if student_name != '同学' else
        '尊敬的同学、同学家长，您好：'
    )
    return f'''
请基于以下霍兰德职业兴趣测评结果，为学生生成一份“高考志愿填报职业兴趣深度报告”。
要求：
0. 报告正文第一段必须是：「{greeting}」，然后空一行再写后续内容。
0.1 禁止使用「好的」「当然」「没问题」等口语作为开头。
1. 不承诺录取，不使用“保证”“一定”等词。
2. 分为：兴趣画像、专业方向建议、职业发展方向、与当前成绩的填报策略、需要规避的误区、下一步行动建议。
3. 语言面向学生和家长，结构清晰，控制在 700 字以内。
4. 必须强调测评仅作辅助，最终需结合位次、选科、招生计划与家庭情况。

学生信息：
省份：{profile.get('province', '')}
选科：{profile.get('subjectCombination', profile.get('subject_combination', ''))}
分数：{profile.get('score', '')}
位次：{profile.get('rank', '')}
目标批次：{profile.get('targetBatch', profile.get('target_batch', ''))}

霍兰德测评数据：
{context}
'''
