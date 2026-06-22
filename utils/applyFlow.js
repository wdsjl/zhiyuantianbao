const { migrateLegacyResult } = require('./personality');
const { isArtSportsActive } = require('./henanArtSports');

const STEPS = [
  { key: 'profile', title: '完善档案', desc: '填写分数、位次、选科和批次' },
  { key: 'personality', title: '霍兰德测评', desc: '完成 30 题职业兴趣测评' },
  { key: 'preferences', title: '填写需求', desc: '补充意向城市、专业和职业目标' },
  { key: 'report', title: '生成报告', desc: 'AI 生成个性化填报策略报告' },
  { key: 'volunteer', title: '填报志愿', desc: '智能推荐并生成冲稳保方案' }
];

const ART_SPORTS_STEPS = [
  { key: 'profile', title: '完善艺体档案', desc: '填写文化课、专业统考分与双过线信息' },
  { key: 'artSportsPool', title: '综合分对标', desc: '按历年最低综合分检索冲稳保院校' },
  { key: 'personality', title: '霍兰德测评', desc: '完成 30 题职业兴趣测评（可选）' },
  { key: 'volunteer', title: '填报志愿', desc: '按综合分生成64个「专业+院校」平行志愿方案' }
];

const ROUTES = {
  profile: '/pages/profile/profile',
  personality: '/pages/personality/personality',
  preferences: '/pages/student-report/student-report',
  report: '/pages/student-report/student-report',
  volunteer: '/pages/volunteer/volunteer',
  artSportsPool: '/pages/eligible-pool/eligible-pool'
};

function isProfileComplete(profile) {
  const base = Boolean(
    profile &&
    profile.province &&
    profile.subjectCombination &&
    profile.score &&
    profile.targetBatch
  );
  if (!base) return false;
  if (isArtSportsActive(profile)) {
    return Boolean(profile.professionalScore || profile.professional_score);
  }
  return Boolean(profile.rank);
}

function isArtSportsPoolDone() {
  const summary = wx.getStorageSync('eligiblePoolSummary') || {};
  return Number(summary.total || 0) > 0;
}

function isPersonalityComplete() {
  const result = wx.getStorageSync('personalityResult');
  return Boolean(result && (result.code || migrateLegacyResult(result).code));
}

function isPreferencesFilled() {
  const prefs = wx.getStorageSync('studentPreferences') || {};
  const fields = [
    prefs.preferredCitiesText,
    prefs.preferredMajorTypesText,
    prefs.preferredMajorsText,
    prefs.careerGoal,
    prefs.otherNotes
  ];
  return fields.some((item) => String(item || '').trim());
}

function isReportGenerated() {
  return Boolean(wx.getStorageSync('studentAiReport'));
}

function isVolunteerGenerated() {
  const plan = wx.getStorageSync('currentPlan') || [];
  return plan.length > 0;
}

function getFlowStatus(profile) {
  const artSports = isArtSportsActive(profile);
  const stepDefs = artSports ? ART_SPORTS_STEPS : STEPS;
  const checks = artSports
    ? {
      profile: isProfileComplete(profile),
      artSportsPool: isArtSportsPoolDone(),
      personality: isPersonalityComplete(),
      volunteer: isVolunteerGenerated()
    }
    : {
      profile: isProfileComplete(profile),
      personality: isPersonalityComplete(),
      preferences: isPreferencesFilled(),
      report: isReportGenerated(),
      volunteer: isVolunteerGenerated()
    };
  const steps = stepDefs.map((step, index) => ({
    ...step,
    index: index + 1,
    done: checks[step.key],
    route: ROUTES[step.key]
  }));
  const completedCount = steps.filter((step) => step.done).length;
  const currentStep = steps.find((step) => !step.done) || steps[steps.length - 1];
  return {
    steps,
    checks,
    completedCount,
    totalCount: steps.length,
    progressPercent: Math.round((completedCount / steps.length) * 100),
    currentStep,
    allDone: completedCount === steps.length
  };
}

function navigateToStep(stepKey) {
  const route = ROUTES[stepKey];
  if (!route) return;
  if (stepKey === 'volunteer' || stepKey === 'artSportsPool') {
    if (stepKey === 'volunteer') {
      wx.switchTab({ url: route });
      return;
    }
    wx.navigateTo({ url: route });
    return;
  }
  wx.navigateTo({ url: route });
}

function goNextStep(profile) {
  const { currentStep } = getFlowStatus(profile);
  navigateToStep(currentStep.key);
}

module.exports = {
  STEPS,
  getFlowStatus,
  navigateToStep,
  goNextStep,
  isProfileComplete,
  isPersonalityComplete,
  isPreferencesFilled,
  isReportGenerated,
  isVolunteerGenerated
};
