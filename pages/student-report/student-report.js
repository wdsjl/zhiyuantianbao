const { request } = require('../../utils/request');
const { requirePermission, getCurrentUserId, fetchEntitlements } = require('../../utils/membership');
const {
  openPdfFromPost,
  preparePdfFromPost,
  sharePdfToWeChat,
  buildStudentPdfFileName
} = require('../../utils/pdfExport');
const { formatReportContent } = require('../../utils/reportFormat');
const { confirmReportBeanDeduction, consumeReportBeans } = require('../../utils/reportBean');
const { loadActiveProfileSync, refreshActiveProfile, resolveStudentId } = require('../../utils/profileHelper');
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
  const limit = Math.min(plan.length, 48);
  const lines = plan.slice(0, limit).map((item, index) => (
    `${index + 1}. ${item.gradientType || item.gradient_type || ''} ${item.schoolName || item.school_name || ''} - ${item.majorName || item.major_name || ''}`
  ));
  const riskText = risk
    ? `风险等级：${risk.level || ''}；冲${risk.chong || 0} 稳${risk.wen || 0} 保${risk.bao || 0} 垫${risk.dian || 0}；共 ${plan.length} 个志愿单位`
    : `共 ${plan.length} 个志愿单位`;
  if (plan.length > limit) {
    return `${riskText}\n（摘要展示前 ${limit} 条）\n${lines.join('\n')}`.trim();
  }
  return `${riskText}\n${lines.join('\n')}`.trim();
}

Page({
  data: {
    profile: {},
    personality: {},
    preferences: defaultPreferences(),
    report: '',
    loading: false,
    pdfReady: false,
    pdfFileName: ''
  },
  onShow() {
    fetchEntitlements().catch(() => {});
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
    const profile = this.data.profile || loadActiveProfileSync();
    const savedReport = formatReportContent(wx.getStorageSync('studentAiReport') || '', profile);
    if (savedReport) wx.setStorageSync('studentAiReport', savedReport);
    this.setData({ personality, preferences: mergedPrefs, report: savedReport, pdfReady: false, pdfFileName: '' });
    this._pdfFilePath = '';
    this._pdfFileName = '';
  },
  loadServerReport() {
    const profile = this.data.profile || loadActiveProfileSync();
    const studentId = resolveStudentId(profile);
    if (!studentId) return;
    request({ url: `/api/ai/student-report?student_id=${studentId}` })
      .then((res) => {
        if (res.report && res.report.report_content) {
          const report = formatReportContent(res.report.report_content, profile);
          wx.setStorageSync('studentAiReport', report);
          this.setData({ report });
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
    confirmReportBeanDeduction('个性化填报报告').then((confirmed) => {
      if (!confirmed) return;
      consumeReportBeans('个性化填报报告')
        .then(() => requirePermission('personality_deep', '个性化填报报告', { consume: false }))
        .then((allowed) => {
          if (!allowed) return;
          this.doGenerateReport();
        })
        .catch((error) => {
          wx.showToast({ title: error.message || '星鼎豆扣除失败', icon: 'none' });
        });
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
        student_id: resolveStudentId(profile),
        user_id: getCurrentUserId() ? Number(getCurrentUserId()) : null,
        profile,
        personality: this.data.personality,
        preferences,
        volunteer_summary: buildVolunteerSummary()
      }
    })
      .then((res) => {
        const report = formatReportContent(res.report || '', profile);
        wx.setStorageSync('studentAiReport', report);
        this.setData({ report, pdfReady: false, pdfFileName: '' });
        this._pdfFilePath = '';
        this._pdfFileName = '';
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
  },
  canExportPdf() {
    const profile = this.data.profile || loadActiveProfileSync();
    if (!this.data.report) {
      wx.showToast({ title: '请先生成报告', icon: 'none' });
      return null;
    }
    if (!resolveStudentId(profile)) {
      wx.showToast({ title: '请先保存学生档案', icon: 'none' });
      return null;
    }
    return profile;
  },
  generateReportPdf() {
    const profile = this.canExportPdf();
    if (!profile) return;
    requirePermission('personality_deep', '个性化填报报告', { consume: false }).then((allowed) => {
      if (!allowed) return;
      const studentId = resolveStudentId(profile);
      const report = formatReportContent(this.data.report, profile);
      preparePdfFromPost('/api/ai/student-report/pdf', {
        student_id: studentId,
        report_content: report
      }, {
        fileName: buildStudentPdfFileName(profile, '个性化报告')
      })
        .then(({ filePath, fileName }) => {
          this._pdfFilePath = filePath;
          this._pdfFileName = fileName;
          this.setData({ pdfReady: true, pdfFileName: fileName });
          wx.showToast({ title: '已生成，请点②发送', icon: 'success' });
        })
        .catch((error) => {
          wx.showToast({ title: error.message || '生成失败', icon: 'none' });
        });
    });
  },
  sendReportPdfToWeChat() {
    if (!this._pdfFilePath || !this._pdfFileName) {
      wx.showToast({ title: '请先点①生成PDF', icon: 'none' });
      return;
    }
    sharePdfToWeChat(this._pdfFilePath, this._pdfFileName)
      .then(() => wx.showToast({ title: '请选择文件传输助手', icon: 'none' }))
      .catch((error) => wx.showToast({ title: error.message || '发送失败', icon: 'none' }));
  },
  previewReportPdf() {
    const profile = this.data.profile || loadActiveProfileSync();
    const studentId = resolveStudentId(profile);
    if (!this.data.report) {
      wx.showToast({ title: '请先生成报告', icon: 'none' });
      return;
    }
    if (!studentId) {
      wx.showToast({ title: '请先保存学生档案', icon: 'none' });
      return;
    }
    requirePermission('personality_deep', '个性化填报报告', { consume: false }).then((allowed) => {
      if (!allowed) return;
      openPdfFromPost('/api/ai/student-report/pdf', {
        student_id: studentId,
        report_content: formatReportContent(this.data.report, profile)
      }, {
        fileName: buildStudentPdfFileName(profile, '个性化报告'),
        mode: 'preview'
      }).catch((error) => {
        wx.showToast({ title: error.message || '导出失败', icon: 'none' });
      });
    });
  }
});
