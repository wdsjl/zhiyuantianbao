const { loadActiveProfileSync } = require('./profileHelper');

const STORAGE_KEYS = {
  report: 'studentAiReport',
  reportSnapshot: 'studentAiReportSnapshot',
  plan: 'currentPlan',
  planSnapshot: 'currentPlanSnapshot',
  aiExplain: 'currentAiExplain',
  risk: 'currentRiskResult',
  draftId: 'currentDraftId',
  draftName: 'currentDraftName'
};

function buildProfileSnapshot(profile) {
  if (!profile) return '';
  return [
    profile.province || '',
    profile.targetBatch || profile.target_batch || '',
    profile.subjectCombination || profile.subject_combination || '',
    String(profile.score ?? ''),
    String(profile.rank ?? '')
  ].join('|');
}

function getCurrentProfileSnapshot() {
  return buildProfileSnapshot(loadActiveProfileSync());
}

function isSnapshotCurrent(snapshot, profile) {
  if (!snapshot) return false;
  return snapshot === buildProfileSnapshot(profile);
}

function clearDerivedArtifacts() {
  wx.removeStorageSync(STORAGE_KEYS.report);
  wx.removeStorageSync(STORAGE_KEYS.reportSnapshot);
  wx.removeStorageSync(STORAGE_KEYS.plan);
  wx.removeStorageSync(STORAGE_KEYS.planSnapshot);
  wx.removeStorageSync(STORAGE_KEYS.aiExplain);
  wx.removeStorageSync(STORAGE_KEYS.risk);
  wx.removeStorageSync(STORAGE_KEYS.draftId);
  wx.removeStorageSync(STORAGE_KEYS.draftName);
}

function saveReportArtifact(report, profile) {
  wx.setStorageSync(STORAGE_KEYS.report, report);
  wx.setStorageSync(STORAGE_KEYS.reportSnapshot, buildProfileSnapshot(profile));
}

function savePlanArtifact(plan, profile) {
  wx.setStorageSync(STORAGE_KEYS.plan, plan);
  wx.setStorageSync(STORAGE_KEYS.planSnapshot, buildProfileSnapshot(profile));
}

function loadReportIfCurrent(profile) {
  const report = wx.getStorageSync(STORAGE_KEYS.report) || '';
  const snapshot = wx.getStorageSync(STORAGE_KEYS.reportSnapshot) || '';
  if (!report) return { report: '', stale: false };
  if (!isSnapshotCurrent(snapshot, profile)) {
    return { report: '', stale: true };
  }
  return { report, stale: false };
}

function loadPlanIfCurrent(profile) {
  const plan = wx.getStorageSync(STORAGE_KEYS.plan) || [];
  const snapshot = wx.getStorageSync(STORAGE_KEYS.planSnapshot) || '';
  if (!plan.length) return { plan: [], aiExplain: '', stale: false };
  if (!isSnapshotCurrent(snapshot, profile)) {
    return { plan: [], aiExplain: '', stale: true };
  }
  const aiExplain = wx.getStorageSync(STORAGE_KEYS.aiExplain) || '';
  return { plan, aiExplain, stale: false };
}

function invalidatePlanArtifacts() {
  wx.removeStorageSync(STORAGE_KEYS.plan);
  wx.removeStorageSync(STORAGE_KEYS.planSnapshot);
  wx.removeStorageSync(STORAGE_KEYS.aiExplain);
  wx.removeStorageSync(STORAGE_KEYS.risk);
  wx.removeStorageSync(STORAGE_KEYS.draftId);
  wx.removeStorageSync(STORAGE_KEYS.draftName);
}

module.exports = {
  STORAGE_KEYS,
  buildProfileSnapshot,
  getCurrentProfileSnapshot,
  isSnapshotCurrent,
  clearDerivedArtifacts,
  saveReportArtifact,
  savePlanArtifact,
  loadReportIfCurrent,
  loadPlanIfCurrent,
  invalidatePlanArtifacts
};
