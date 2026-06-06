const { request } = require('../../utils/request');
const { requirePermission, getCurrentUserId } = require('../../utils/membership');
const { loadActiveProfileSync, refreshActiveProfile } = require('../../utils/profileHelper');
const { migrateLegacyResult } = require('../../utils/personality');

const PREF_STORAGE_KEY = 'studentPreferences';

function splitText(value) {
  if (!value || !String(value).trim()) return [];
  return String(value)
    .split(/[,，、;；\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function defaultPreferences() {
  return {
    preferredCitiesText: '',
    preferredMajorTypesText: '',
    preferredMajorsText: '',
    avoidDirectionsText: '',
    schoolLevelPreference: '',
    schoolNaturePreference: '',
    tuitionBudget: '',
    careerGoal: '',
    acceptAdjustment: '',
    otherNotes: ''
  };
}

function buildPreferencesPayload(form) {
  return {
    preferredCities: splitText(form.preferredCitiesText),
    preferredMajorTypes: splitText(form.preferredMajorTypesText),
    preferredMajors: splitText(form.preferredMajorsText),
    avoidDirections: splitText(form.avoidDirectionsText),
    schoolLevelPreference: form.schoolLevelPreference || '',
    schoolNaturePreference: form.schoolNaturePreference || '',
    tuitionBudget: form.tuitionBudget || '',
    careerGoal: form.careerGoal || '',
    acceptAdjustment: form.acceptAdjustment || '',
    otherNotes: form.otherNotes || ''
  };
}

function buildVolunteerSummary() {
  const plan = wx.getStorageSync('currentPlan') || [];
  const risk = wx.getStorageSync('currentRiskResult') || null;
  if (!plan.length) return '';
  const lines = plan.slice(0, 8).map((item, index) => (
    `${index + 1}. ${item.gradientType || item.gradient_type || ''} ${item.schoolName || item.school_name || ''} - ${item.majorName || item.major_name || ''}`
  ));
  const riskText = risk
    ? `风险等级：${risk.level || ''}；冲${risk.chong || 0} 稳${risk.wen || 0} 保${risk.bao || 0} 垫${risk.dian || 0}`
    : '';
  return `${riskText}\n${lines.join('\n')}`.trim();
}

Page({
  data: {
    profile: {},
    personality: {},
    preferences: defaultPreferences(),
    report: '',
    loading: false
  },
  onShow() {
    refreshActiveProfile().then((profile) => {
      this.setData({ profile: profile || loadActiveProfileSync() });
      this.loadServerReport();
    });
    let personality = wx.getStorageSync('personalityResult') || {};
    if (personality.code) personality = migrateLegacyResult(personality);
    const aiCareerReport = wx.getStorageSync('personalityAiCareerReport') || '';
    if (aiCareerReport) personality = { ...personality, aiCareerReport };
    const savedPrefs = wx.getStorageSync(PREF_STORAGE_KEY) || defaultPreferences();
    const mergedPrefs = { ...defaultPreferences(), ...savedPrefs };
    if (!mergedPrefs.preferredMajorTypesText && personality.majorTypes && personality.majorTypes.length) {
      mergedPrefs.preferredMajorTypesText = personality.majorTypes.join('、');
      wx.setStorageSync(PREF_STORAGE_KEY, mergedPrefs);
    }
    const savedReport = wx.getStorageSync('studentAiReport') || '';
    this.setData({ personality, preferences: mergedPrefs, report: savedReport });
  },
  loadServerReport() {
    const profile = this.data.profile || loadActiveProfileSync();
    const studentId = profile.studentId || profile.student_id;
    if (!studentId) return;
    request({ url: '/api/ai/student-report', data: { student_id: Number(studentId) } })
      .then((res) => {
        if (res.report && res.report.report_content) {
          wx.setStorageSync('studentAiReport', res.report.report_content);
          this.setData({ report: res.report.report_content });
        }
      })
      .catch(() => {});
  },
  onPrefInput(event) {
    const field = event.currentTarget.dataset.field;
    const preferences = { ...this.data.preferences, [field]: event.detail.value };
    this.setData({ preferences });
    wx.setStorageSync(PREF_STORAGE_KEY, preferences);
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' });
  },
  goPersonality() {
    wx.navigateTo({ url: '/pages/personality/personality' });
  },
  goVolunteer() {
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  },
  validateBeforeGenerate() {
    const { profile, personality } = this.data;
    if (!profile.province || !profile.score || !profile.rank || !profile.subjectCombination || !profile.targetBatch) {
      wx.showModal({
        title: '请先完善档案',
        content: '生成报告需要省份、分数、位次、选科和批次信息。',
        confirmText: '去完善',
        success: (res) => { if (res.confirm) this.goProfile(); }
      });
      return false;
    }
    if (!personality.code) {
      wx.showModal({
        title: '请先完成测评',
        content: '需要霍兰德职业兴趣测评结果，才能生成个性化报告。',
        confirmText: '去测评',
        success: (res) => { if (res.confirm) this.goPersonality(); }
      });
      return false;
    }
    return true;
  },
  generateReport() {
    if (!this.validateBeforeGenerate()) return;
    requirePermission('personality_deep', '个性化填报报告', { consume: true }).then((allowed) => {
      if (!allowed) return;
      this.doGenerateReport();
    });
  },
  doGenerateReport() {
    const profile = this.data.profile;
    const preferences = buildPreferencesPayload(this.data.preferences);
    this.setData({ loading: true });
    request({
      url: '/api/ai/student-report',
      method: 'POST',
      data: {
        student_id: profile.studentId ? Number(profile.studentId) : null,
        user_id: getCurrentUserId() ? Number(getCurrentUserId()) : null,
        profile,
        personality: this.data.personality,
        preferences,
        volunteer_summary: buildVolunteerSummary()
      }
    })
      .then((res) => {
        const report = res.report || '';
        wx.setStorageSync('studentAiReport', report);
        this.setData({ report });
        wx.showToast({ title: '报告已生成', icon: 'success' });
        setTimeout(() => {
          wx.showModal({
            title: '报告已生成',
            content: '下一步可进入志愿填报页，结合报告结果智能生成冲稳保方案。',
            confirmText: '去填报志愿',
            cancelText: '稍后',
            success: (modalRes) => {
              if (modalRes.confirm) wx.switchTab({ url: '/pages/volunteer/volunteer' });
            }
          });
        }, 600);
      })
      .catch((error) => {
        wx.showToast({ title: error.message || '生成失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },
  copyReport() {
    if (!this.data.report) return;
    wx.setClipboardData({ data: this.data.report });
  }
});
