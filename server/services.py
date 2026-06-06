SUBJECT_KEYWORDS = ('物理', '化学', '生物', '历史', '政治', '地理', '技术')


def matches_subject_requirement(student_combination: str, requirement: str | None) -> bool:
    if not requirement or requirement.strip() in ('不限', '无要求', '无', '-', '—'):
        return True
    combo = (student_combination or '').replace('/', '+').replace('、', '+').replace(',', '+')
    req = requirement.replace('/', '+').replace('、', '+').replace(',', '+')
    required = [subject for subject in SUBJECT_KEYWORDS if subject in req]
    if not required:
        return True
    return all(subject in combo for subject in required)


def get_gradient_type(
    user_rank: int,
    min_rank: int | None,
    segment: str = 'mid',
    batch: str = '',
) -> str:
    from rank_strategy_service import classify_gradient
    return classify_gradient(user_rank, min_rank, segment, batch)


def get_risk_level(gradient_type: str, is_adjustable: bool) -> str:
    if gradient_type == '冲' and not is_adjustable:
        return '高'
    if gradient_type == '冲':
        return '中'
    if not is_adjustable:
        return '中'
    return '低'


def get_risk_reason(gradient_type: str, is_adjustable: bool) -> str:
    if gradient_type == '冲' and not is_adjustable:
        return '当前志愿为冲刺档，且未选择服从调剂，若专业分数不足，存在较高退档风险。'
    if gradient_type == '冲':
        return '院校往年录取位次高于当前位次，建议保留稳妥志愿兜底。'
    if not is_adjustable:
        return '未选择服从调剂，达到院校投档线后仍可能因专业未录取而退档。'
    return '当前志愿结构相对稳妥，仍需以考试院和高校官方信息为准。'


def inspect_plan_risk(items: list[dict]) -> dict:
    count = {'冲': 0, '稳': 0, '保': 0, '垫': 0}
    warnings = []
    high_risk_count = 0
    no_adjustment_count = 0

    for item in items:
        gradient_type = item.get('gradient_type') or item.get('gradientType') or '稳'
        is_adjustable = bool(item.get('is_adjustable', item.get('isAdjustable', True)))
        risk_level = item.get('risk_level') or item.get('riskLevel') or get_risk_level(gradient_type, is_adjustable)
        if gradient_type in count:
            count[gradient_type] += 1
        if risk_level == '高':
            high_risk_count += 1
        if not is_adjustable:
            no_adjustment_count += 1

    if count['冲'] > count['保'] + count['垫']:
        warnings.append('冲刺志愿比例偏高，保底和垫底志愿不足，存在滑档风险。')
    if count['保'] + count['垫'] < 2:
        warnings.append('保底志愿数量不足，建议增加录取位次更稳妥的院校。')
    if no_adjustment_count:
        warnings.append('存在未服从调剂志愿，达到投档线后仍可能因专业未录取而退档。')
    if not items:
        warnings.append('当前条件下暂无可用方案，建议放宽城市、学费或院校类型条件。')

    level = '高' if high_risk_count or len(warnings) > 1 else '中' if warnings else '低'
    if not warnings:
        warnings.append('当前方案中冲稳保垫结构相对合理，仍需以官方填报系统为准。')

    return {
        'level': level,
        'count': count,
        'warnings': warnings
    }
