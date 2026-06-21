import re
from datetime import datetime
from typing import Any
from urllib.parse import quote


PDF_FILENAME_LABELS = {
    'student_report': '个性化报告',
    'career_report': '霍兰德测评报告',
    'volunteer_draft': '填报志愿',
}


def pdf_text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).replace('\r', ' ').replace('\n', ' ')


def hex_text(value: Any) -> str:
    return pdf_text(value).encode('utf-16-be').hex().upper()


def normalize_pdf_filename_part(value: str, fallback: str = '学生') -> str:
    text = pdf_text(value).strip() or fallback
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        text = text.replace(char, '')
    return text.strip() or fallback


def student_display_name(student: dict) -> str:
    return normalize_pdf_filename_part(
        student.get('name') or student.get('student_name') or '',
        '同学'
    )


def build_report_greeting(student: dict) -> str:
    name = student_display_name(student)
    if name == '同学':
        return '尊敬的同学、同学家长，您好：'
    return f'{name}同学、{name}同学家长，您好：'


REPORT_FILLER_PATTERNS = (
    re.compile(r'^好的[，,。！!：:\s]+'),
    re.compile(r'^没问题[，,。！!：:\s]+'),
    re.compile(r'^当然[，,。！!：:\s]+'),
    re.compile(r'^嗯[，,。！!：:\s]+'),
)


def strip_report_filler(body: str) -> str:
    content = str(body or '').strip()
    changed = True
    while changed and content:
        changed = False
        for pattern in REPORT_FILLER_PATTERNS:
            new_content = pattern.sub('', content, count=1).strip()
            if new_content != content:
                content = new_content
                changed = True
                break
    return content


def ensure_report_greeting(body: str, student: dict) -> str:
    content = strip_report_filler(body)
    if not content:
        return build_report_greeting(student)
    name = student_display_name(student)
    head = content[:40]
    if '家长，您好' in head or head.startswith(f'{name}同学'):
        return content
    return f'{build_report_greeting(student)}\n\n{content}'


AI_GENERATED_NOTICE = '人工智能生成'
AI_GENERATED_MARKERS = (AI_GENERATED_NOTICE, 'AI生成')


def append_ai_generated_notice(text: str) -> str:
    content = str(text or '').strip()
    if not content:
        return content
    tail = content[-120:]
    if any(marker in tail for marker in AI_GENERATED_MARKERS):
        return content
    return f'{content}\n\n—— {AI_GENERATED_NOTICE}'


def build_student_pdf_filename(student: dict, kind: str) -> str:
    name = normalize_pdf_filename_part(student.get('name') or student.get('student_name') or '')
    label = PDF_FILENAME_LABELS.get(kind, '报告')
    return f'{name}的{label}.pdf'


def escape_pdf_name(value: str) -> str:
    return normalize_pdf_filename_part(value, '导出')


def pdf_content_disposition(filename: str) -> str:
    base = filename[:-4] if filename.lower().endswith('.pdf') else filename
    full_name = f'{normalize_pdf_filename_part(base, "导出")}.pdf'
    ascii_fallback = full_name if full_name.isascii() else 'report.pdf'
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quote(full_name)}'


def pdf_header_filename(filename: str) -> str:
    """HTTP 响应头必须是 latin-1；中文文件名用百分号编码。"""
    base = filename[:-4] if filename.lower().endswith('.pdf') else filename
    full_name = f'{normalize_pdf_filename_part(base, "导出")}.pdf'
    if full_name.isascii():
        return full_name
    return quote(full_name)

def wrap_text(value: Any, max_chars: int) -> list[str]:
    text = pdf_text(value)
    if not text:
        return ['']
    return [text[index:index + max_chars] for index in range(0, len(text), max_chars)]


def lines_from_paragraphs(text: str, max_chars: int = 52) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or '').splitlines():
        stripped = paragraph.strip()
        if not stripped:
            lines.append('')
            continue
        lines.extend(wrap_text(stripped, max_chars))
    return lines


def build_text_report_pdf(title: str, student: dict, body: str) -> bytes:
    lines: list[str] = [
        title,
        f'导出时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        (
            f'姓名：{student.get("name", "")}    省份：{student.get("province", "")}    '
            f'选科：{student.get("subject_combination", "")}'
        ),
        (
            f'分数：{student.get("score", "")}    位次：{student.get("rank", "")}    '
            f'批次：{student.get("target_batch", "")}'
        ),
        '提示：本报告由 AI 基于用户填写数据生成，仅供参考，不构成录取承诺。',
        '',
        '—— 报告正文 ——',
    ]
    lines.extend(lines_from_paragraphs(append_ai_generated_notice(ensure_report_greeting(body, student)), 52))
    lines.extend([
        '',
        '—— 免责声明 ——',
        '本系统基于历史数据、测评结果与用户输入进行辅助分析。请考生和家长以各省教育考试院、高校招生章程和正式填报系统为准。',
    ])
    return build_pdf(lines)


def build_pdf(lines: list[str]) -> bytes:
    page_width = 595
    page_height = 842
    margin_x = 42
    top_y = 800
    line_height = 18
    bottom_y = 42
    pages: list[list[str]] = []
    current: list[str] = []
    y = top_y
    for line in lines:
        if y < bottom_y:
            pages.append(current)
            current = []
            y = top_y
        current.append(line)
        y -= line_height
    if current:
        pages.append(current)

    objects: list[bytes] = []

    def add_object(content: str | bytes) -> int:
        if isinstance(content, str):
            content = content.encode('latin-1')
        objects.append(content)
        return len(objects)

    font_descriptor = add_object('<< /Type /FontDescriptor /FontName /STSong-Light /Flags 4 /Ascent 880 /Descent -120 /CapHeight 700 /ItalicAngle 0 /StemV 80 >>')
    cid_font = add_object(f'<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> /FontDescriptor {font_descriptor} 0 R >>')
    type0_font = add_object(f'<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [{cid_font} 0 R] >>')

    page_object_ids: list[int] = []
    pending_pages: list[tuple[int, int]] = []
    for page_lines in pages:
        y = top_y
        commands = ['BT', f'/{"F1"} 11 Tf', '14 TL']
        for line in page_lines:
            safe_line = hex_text(line)
            commands.append(f'1 0 0 1 {margin_x} {y} Tm <{safe_line}> Tj')
            y -= line_height
        commands.append('ET')
        stream = '\n'.join(commands).encode('latin-1')
        content_id = add_object(b'<< /Length ' + str(len(stream)).encode('latin-1') + b' >>\nstream\n' + stream + b'\nendstream')
        page_id = add_object(b'')
        page_object_ids.append(page_id)
        pending_pages.append((page_id, content_id))

    kids = ' '.join(f'{page_id} 0 R' for page_id in page_object_ids)
    pages_id = add_object(f'<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>')

    for page_id, content_id in pending_pages:
        objects[page_id - 1] = (
            f'<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page_width} {page_height}] '
            f'/Resources << /Font << /F1 {type0_font} 0 R >> >> /Contents {content_id} 0 R >>'
        ).encode('latin-1')

    catalog_id = add_object(f'<< /Type /Catalog /Pages {pages_id} 0 R >>')

    output = bytearray(b'%PDF-1.4\n%\xE2\xE3\xCF\xD3\n')
    offsets = [0]
    for index, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f'{index} 0 obj\n'.encode('latin-1'))
        output.extend(content)
        output.extend(b'\nendobj\n')
    xref_offset = len(output)
    output.extend(f'xref\n0 {len(objects) + 1}\n'.encode('latin-1'))
    output.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode('latin-1'))
    output.extend(f'trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF'.encode('latin-1'))
    return bytes(output)


def is_art_sports_student(student: dict, draft: dict) -> bool:
    if student.get('waive_art_sports_batch'):
        return False
    exam_type = str(student.get('exam_type') or '')
    if exam_type in ('艺术类', '体育类'):
        return True
    batch = str(draft.get('batch') or student.get('target_batch') or '')
    return ('艺术' in batch) or ('体育' in batch)


def format_draft_item_lines(item: dict, *, art_sports: bool) -> list[str]:
    """每条志愿独立成块，避免长专业名挤乱单行表格。"""
    lines: list[str] = []
    order = pdf_text(item.get('sort_order'))
    gradient = pdf_text(item.get('gradient_type'))
    lines.append(f'【志愿 {order}】梯度：{gradient}')

    school_code = pdf_text(item.get('school_code'))
    school_name = pdf_text(item.get('school_name'))
    if school_code:
        lines.extend(wrap_text(f'院校：{school_code} / {school_name}', 52))
    else:
        lines.extend(wrap_text(f'院校：{school_name}', 52))

    major_code = pdf_text(item.get('major_code'))
    major_name = pdf_text(item.get('major_name'))
    if major_code:
        lines.extend(wrap_text(f'专业：{major_code} / {major_name}', 52))
    else:
        lines.extend(wrap_text(f'专业：{major_name}', 52))

    detail_parts: list[str] = []
    city = pdf_text(item.get('city'))
    if city:
        detail_parts.append(f'城市：{city}')
    tuition = item.get('tuition')
    if tuition not in (None, ''):
        detail_parts.append(f'学费：{tuition}')
    duration = pdf_text(item.get('duration'))
    if duration:
        detail_parts.append(f'学制：{duration}')
    detail_parts.append(f'调剂：{"是" if item.get("is_adjustable") else "否"}')
    risk_level = pdf_text(item.get('risk_level'))
    if risk_level:
        detail_parts.append(f'风险：{risk_level}')
    if detail_parts:
        lines.extend(wrap_text('    '.join(detail_parts), 52))

    reason = pdf_text(item.get('risk_reason'))
    if reason:
        prefix = '对标说明' if art_sports and '综合分' in reason else '风险说明'
        lines.extend(wrap_text(f'{prefix}：{reason}', 52))
    lines.append('')
    return lines


def build_draft_pdf(draft: dict, student: dict, items: list[dict]) -> bytes:
    art_sports = is_art_sports_student(student, draft)
    lines: list[str] = []
    lines.extend([
        '智愿填报志愿方案',
        f'导出时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '提示：本方案仅供参考，最终以各省教育考试院和高校官方公布及正式填报系统为准。',
        '',
        build_report_greeting(student),
        '',
        '一、学生信息',
        f'姓名：{student.get("name", "")}    省份：{student.get("province", "")}    城市：{student.get("city", "")}',
        f'学校：{student.get("school_name", "")}    年级：{student.get("grade", "")}    班级：{student.get("class_name", "")}',
        f'年份：{student.get("exam_year", "")}    选科：{student.get("subject_combination", "")}    批次：{draft.get("batch", student.get("target_batch", ""))}',
    ])
    if art_sports:
        lines.append(
            f'文化分：{draft.get("score", student.get("score", ""))}    '
            f'专业统考分：{student.get("professional_score", "")}    '
            f'考试类别：{student.get("exam_type", "")}'
        )
        lines.append('说明：艺体批次无官方综合分位次，方案按历年最低综合分对标生成。')
    else:
        lines.append(
            f'分数：{draft.get("score", student.get("score", ""))}    位次：{draft.get("rank", student.get("rank", ""))}'
        )
    lines.extend([
        '',
        '二、方案概览',
        f'方案名称：{draft.get("draft_name", "")}    风险等级：{draft.get("risk_level", "未排查")}',
        f'省份：{draft.get("province", "")}    年份：{draft.get("year", "")}    批次：{draft.get("batch", "")}',
        '',
        '三、志愿明细',
    ])
    if not items:
        lines.append('（暂无志愿）')
    for item in items:
        lines.extend(format_draft_item_lines(item, art_sports=art_sports))
    if draft.get('ai_explain'):
        lines.extend(['', '四、AI 志愿方案解读'])
        for paragraph in append_ai_generated_notice(str(draft.get('ai_explain') or '')).splitlines():
            lines.extend(wrap_text(paragraph, 52))
        disclaimer_title = '五、免责声明'
    else:
        disclaimer_title = '四、免责声明'
    lines.extend(['', disclaimer_title, '本系统基于历史数据、位次和风险规则进行辅助分析，不构成录取承诺。请考生和家长以官方政策、招生章程、正式填报系统为准。'])
    return build_pdf(lines)
