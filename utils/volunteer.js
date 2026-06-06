const { schools } = require('./mockData');

const GRADIENT_CLASS_MAP = {
  冲: 'chong',
  稳: 'wen',
  保: 'bao',
  垫: 'dian'
};

function getGradientClass(gradientType) {
  return GRADIENT_CLASS_MAP[gradientType] || 'wen';
}

function getGradientType(userRank, schoolRank) {
  if (!userRank || !schoolRank) return '稳';
  const rank = Number(schoolRank);
  const x = Number(userRank);
  if (rank >= x * 0.9 && rank <= x * 0.95) return '冲';
  if (rank >= x * 0.95 && rank <= x * 1.05) return '稳';
  if (rank >= x * 1.15 && rank <= x * 1.25) return '保';
  if (rank < x * 0.9) return '冲';
  if (rank > x * 1.25) return '垫';
  return '稳';
}

function getRiskLevel(item) {
  if (item.gradientType === '冲' && !item.isAdjustable) return '高';
  if (item.gradientType === '冲') return '中';
  if (!item.isAdjustable) return '中';
  return '低';
}

function getRiskReason(item) {
  if (item.gradientType === '冲' && !item.isAdjustable) {
    return '当前志愿为冲刺档，且未选择服从调剂，若专业分数不足，存在较高退档风险。';
  }
  if (item.gradientType === '冲') {
    return '院校往年录取位次高于当前位次，建议保留稳妥志愿兜底。';
  }
  if (!item.isAdjustable) {
    return '未选择服从调剂，达到院校投档线后仍可能因专业未录取而退档。';
  }
  return '当前志愿结构相对稳妥，仍需以考试院和高校官方信息为准。';
}

function generateVolunteerPlan(profile, preferences = {}) {
  const rank = Number(profile.rank || 0);
  const preferredCities = preferences.cities || [];
  const preferredTypes = preferences.schoolTypes || [];
  const preferredMajors = preferences.majorTypes || [];

  const candidates = schools.filter((school) => {
    const matchCity = !preferredCities.length || preferredCities.includes(school.city);
    const matchType = !preferredTypes.length || preferredTypes.includes(school.type);
    const matchMajor = !preferredMajors.length || school.majors.some((major) => preferredMajors.includes(major));
    return matchCity && matchType && matchMajor;
  });

  return candidates.map((school, index) => {
    const gradientType = getGradientType(rank, school.minRank);
    const item = {
      id: `${school.id}-${index}`,
      sortOrder: index + 1,
      gradientType,
      gradientClass: getGradientClass(gradientType),
      schoolId: school.id,
      schoolName: school.name,
      schoolCode: school.code,
      majorName: school.majors[0],
      majorCode: `M${index + 100}`,
      city: school.city,
      schoolType: school.type,
      tags: school.tags,
      tuition: school.tuition,
      duration: school.duration,
      isAdjustable: true
    };
    item.riskLevel = getRiskLevel(item);
    item.riskReason = getRiskReason(item);
    return item;
  });
}

function inspectPlanRisk(plan) {
  const count = { 冲: 0, 稳: 0, 保: 0, 垫: 0 };
  plan.forEach((item) => {
    count[item.gradientType] += 1;
  });

  const highRiskItems = plan.filter((item) => item.riskLevel === '高');
  const noAdjustableItems = plan.filter((item) => !item.isAdjustable);
  const warnings = [];

  if (count['冲'] > count['保'] + count['垫']) {
    warnings.push('冲刺志愿比例偏高，保底和垫底志愿不足，存在滑档风险。');
  }
  if (count['保'] + count['垫'] < 2) {
    warnings.push('保底志愿数量不足，建议增加录取位次更稳妥的院校。');
  }
  if (noAdjustableItems.length) {
    warnings.push('存在未服从调剂志愿，达到投档线后仍可能因专业未录取而退档。');
  }
  if (!plan.length) {
    warnings.push('当前条件下暂无可用方案，建议放宽城市、学费或院校类型条件。');
  }

  return {
    level: highRiskItems.length || warnings.length > 1 ? '高' : warnings.length ? '中' : '低',
    count,
    warnings: warnings.length ? warnings : ['当前方案中冲稳保垫结构相对合理，仍需以官方填报系统为准。']
  };
}

module.exports = {
  generateVolunteerPlan,
  inspectPlanRisk,
  getRiskLevel,
  getRiskReason,
  getGradientClass
};
