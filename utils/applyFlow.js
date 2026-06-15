const { migrateLegacyResult } = require('./personality');
const { loadActiveProfileSync } = require('./profileHelper');
const { loadReportIfCurrent, loadPlanIfCurrent, buildProfileSnapshot } = require('./profileSnapshot');

const STEPS = [
  { key: 'profile', title: '完善档案', desc: '填写分数、位次、选科和批次' },
  { key: 'eligible', title: '可报院校', desc: '检索所有符合分数位次的院校专业' },
  { key: 'personality', title: '霍兰德测评', desc: '明确兴趣方向，辅助专业筛选' },
  { key: 'preferences', title: '填写需求', desc: '意向城市、专业、职业目标等' },
  { key: 'report', title: '志愿报告（可选）', desc: 'AI 生成最终填报策略报告' },
  { key: 'volunteer', title: '智能填报', desc: '结合测评与需求生成最终志愿方案' }
];

const ROUTES = {
  profile: '/pages/profile/profile',
  eligible: '/pages/eligible-pool/eligible-pool',
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

function isEligiblePoolReady() {
  const profile = loadActiveProfileSync();
  const snapshot = wx.getStorageSync('eligiblePoolSnapshot') || '';
  const summary = wx.getStorageSync('eligiblePoolSummary') || {};
  return Boolean(snapshot && snapshot === buildProfileSnapshot(profile) && (summary.total || 0) > 0);
}

function getFlowStatus(profile) {
  const checks = {
    profile: isProfileComplete(profile),
    eligible: isEligiblePoolReady(),
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
  isEligiblePoolReady,
  isPersonalityComplete,
  isPreferencesFilled,
  isReportGenerated,
  isVolunteerGenerated
};
