const { migrateLegacyResult } = require('./personality');
const { loadActiveProfileSync } = require('./profileHelper');
const { loadReportIfCurrent, loadPlanIfCurrent } = require('./profileSnapshot');

const STEPS = [
  { key: 'profile', title: '完善档案', desc: '填写分数、位次、选科和批次' },
  { key: 'personality', title: '霍兰德测评', desc: '完成测评，系统自动生成兴趣报告（大数据智能匹配）' },
  { key: 'preferences', title: '填写需求', desc: '补充意向城市、专业和职业目标（可选）' },
  { key: 'report', title: 'AI 报告（可选）', desc: '大模型个性化报告，非必选，可直接填报志愿' },
  { key: 'volunteer', title: '填报志愿', desc: '系统自动生成冲稳保志愿方案（大数据智能匹配）' }
];

const ROUTES = {
  profile: '/pages/profile/profile',
  personality: '/pages/personality/personality',
  preferences: '/pages/student-report/student-report',
  report: '/pages/student-report/student-report',
  volunteer: '/pages/volunteer/volunteer'
};

function isProfileComplete(profile) {
  return Boolean(
    profile &&
    profile.province &&
    profile.subjectCombination &&
    profile.score &&
    profile.rank &&
    profile.targetBatch
  );
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
  const profile = loadActiveProfileSync();
  return Boolean(loadReportIfCurrent(profile).report);
}

function isVolunteerGenerated() {
  const profile = loadActiveProfileSync();
  return (loadPlanIfCurrent(profile).plan || []).length > 0;
}

function getFlowStatus(profile) {
  const checks = {
    profile: isProfileComplete(profile),
    personality: isPersonalityComplete(),
    preferences: isPreferencesFilled(),
    report: isReportGenerated(),
    volunteer: isVolunteerGenerated()
  };
  const steps = STEPS.map((step, index) => ({
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
  if (stepKey === 'volunteer') {
    wx.switchTab({ url: route });
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
