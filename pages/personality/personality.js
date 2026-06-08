const { questions, options, calculateResult, migrateLegacyResult } = require('../../utils/personality');
const { request } = require('../../utils/request');
const { requirePermission, getCurrentUserId } = require('../../utils/membership');
const { openPdfFromPost, buildStudentPdfFileName } = require('../../utils/pdfExport');
const { loadActiveProfileSync, resolveStudentId } = require('../../utils/profileHelper');

function buildQuestions(answers = {}) {
  return questions.map((question) => ({
    ...question,
    selectedValue: answers[question.id] || 0
  }));
}

function syncAssessment(result) {
  const profile = loadActiveProfileSync();
  const userId = getCurrentUserId();
  const studentId = profile.studentId || profile.student_id;
  if (!studentId && !userId) return Promise.resolve(null);
  return request({
    url: '/api/personality/assessment',
    method: 'POST',
    data: {
      student_id: studentId ? Number(studentId) : null,
      user_id: userId ? Number(userId) : null,
      report: result
    }
  }).then((res) => {
    if (res.assessment_id) {
      wx.setStorageSync('personalityAssessmentId', res.assessment_id);
    }
    return res;
  }).catch(() => null);
}

function loadServerAssessment(studentId) {
  if (!studentId) return Promise.resolve(null);
  return request({
    url: '/api/personality/assessment',
    data: { student_id: Number(studentId) }
  }).then((res) => res.assessment || null).catch(() => null);
}

Page({
  data: {
    questions: buildQuestions(),
    options,
    answers: {},
    result: null,
    progress: 0,
    aiCareerReport: '',
    aiLoading: false,
    syncing: false
  },
  onShow() {
    this.bootstrapResult();
  },
  bootstrapResult() {
    let result = wx.getStorageSync('personalityResult') || null;
    if (result) {
      result = migrateLegacyResult(result);
      wx.setStorageSync('personalityResult', result);
    }
    const aiCareerReport = wx.getStorageSync('personalityAiCareerReport') || '';
    this.setData({ result, aiCareerReport });
    const profile = loadActiveProfileSync();
    const studentId = profile.studentId || profile.student_id;
    if (!studentId) return;
    loadServerAssessment(studentId).then((assessment) => {
      if (!assessment) return;
      if (assessment.report) {
        const merged = migrateLegacyResult(assessment.report);
        wx.setStorageSync('personalityResult', merged);
        this.setData({ result: merged });
      }
      if (assessment.ai_career_report) {
        wx.setStorageSync('personalityAiCareerReport', assessment.ai_career_report);
        this.setData({ aiCareerReport: assessment.ai_career_report });
      }
      if (assessment.assessment_id) {
        wx.setStorageSync('personalityAssessmentId', assessment.assessment_id);
      }
    });
  },
  selectOption(event) {
    const questionId = event.currentTarget.dataset.questionId;
    const value = event.currentTarget.dataset.value;
    const answers = { ...this.data.answers, [questionId]: value };
    const progress = Math.round((Object.keys(answers).length / questions.length) * 100);
    this.setData({ answers, progress, questions: buildQuestions(answers) });
  },
  submitTest() {
    if (Object.keys(this.data.answers).length < questions.length) {
      wx.showToast({ title: '请完成全部题目', icon: 'none' });
      return;
    }
    const result = calculateResult(this.data.answers);
    wx.setStorageSync('personalityResult', result);
    wx.removeStorageSync('personalityAiCareerReport');
    this.setData({ result, aiCareerReport: '', syncing: true });
    syncAssessment(result)
      .finally(() => {
        this.setData({ syncing: false });
        wx.showToast({ title: '测评完成', icon: 'success' });
        setTimeout(() => {
          wx.showModal({
            title: '测评完成',
            content: '下一步请填写个人需求并生成 AI 个性化填报报告。',
            confirmText: '去生成报告',
            cancelText: '稍后',
            success: (modalRes) => {
              if (modalRes.confirm) {
                wx.navigateTo({ url: '/pages/student-report/student-report' });
              }
            }
          });
        }, 600);
      });
  },
  generateAiReport() {
    if (!this.data.result) {
      wx.showToast({ title: '请先完成测评', icon: 'none' });
      return;
    }
    requirePermission('personality_deep', '深度职业兴趣报告', { consume: true }).then((allowed) => {
      if (!allowed) return;
      this.doGenerateAiReport();
    });
  },
  doGenerateAiReport() {
    const profile = loadActiveProfileSync();
    this.setData({ aiLoading: true });
    request({
      url: '/api/ai/career-report',
      method: 'POST',
      data: {
        student_id: resolveStudentId(profile),
        user_id: getCurrentUserId() ? Number(getCurrentUserId()) : null,
        assessment_id: wx.getStorageSync('personalityAssessmentId') || null,
        profile,
        personality: {
          ...this.data.result,
          aiCareerReport: this.data.aiCareerReport
        }
      }
    })
      .then((res) => {
        const report = res.report || '';
        wx.setStorageSync('personalityAiCareerReport', report);
        if (res.assessment_id) {
          wx.setStorageSync('personalityAssessmentId', res.assessment_id);
        }
        const enriched = {
          ...this.data.result,
          aiCareerReport: report
        };
        wx.setStorageSync('personalityResult', enriched);
        this.setData({ aiCareerReport: report, result: enriched });
        wx.showToast({ title: '深度报告已生成', icon: 'success' });
      })
      .catch((error) => {
        wx.showToast({ title: error.message || '生成失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ aiLoading: false });
      });
  },
  copyAiReport() {
    if (!this.data.aiCareerReport) {
      wx.showToast({ title: '请先生成深度报告', icon: 'none' });
      return;
    }
    wx.setClipboardData({ data: this.data.aiCareerReport });
  },
  exportAiReportPdf() {
    const profile = loadActiveProfileSync();
    const studentId = resolveStudentId(profile);
    if (!this.data.aiCareerReport) {
      wx.showToast({ title: '请先生成深度报告', icon: 'none' });
      return;
    }
    if (!studentId) {
      wx.showToast({ title: '请先保存学生档案', icon: 'none' });
      return;
    }
    requirePermission('personality_deep', '深度职业兴趣报告', { consume: false }).then((allowed) => {
      if (!allowed) return;
      openPdfFromPost('/api/ai/career-report/pdf', {
        student_id: studentId,
        report_content: this.data.aiCareerReport
      }, {
        fileName: buildStudentPdfFileName(profile, '霍兰德测评报告')
      })
        .then(() => {
          wx.showModal({
            title: 'PDF 已打开',
            content: '点击右上角「…」可转发给微信好友或保存到手机。',
            showCancel: false
          });
        })
        .catch((error) => {
          wx.showToast({ title: error.message || '导出失败', icon: 'none' });
        });
    });
  },
  retest() {
    wx.showModal({
      title: '重新测评',
      content: '重新测评会覆盖当前霍兰德报告与 AI 深度报告，是否继续？',
      success: (res) => {
        if (!res.confirm) return;
        wx.removeStorageSync('personalityResult');
        wx.removeStorageSync('personalityAiCareerReport');
        wx.removeStorageSync('personalityAssessmentId');
        this.setData({
          answers: {},
          result: null,
          progress: 0,
          aiCareerReport: '',
          questions: buildQuestions()
        });
      }
    });
  },
  goStudentReport() {
    if (!this.data.result) {
      wx.showToast({ title: '请先完成测评', icon: 'none' });
      return;
    }
    wx.navigateTo({ url: '/pages/student-report/student-report' });
  },
  goVolunteer() {
    if (!this.data.result) {
      wx.showToast({ title: '请先完成测评', icon: 'none' });
      return;
    }
    if (!wx.getStorageSync('studentAiReport')) {
      wx.showModal({
        title: '建议先生成个性化报告',
        content: '按推荐流程，先生成 AI 个性化报告再填报志愿，策略会更完整。',
        confirmText: '去生成报告',
        cancelText: '直接去志愿',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({ url: '/pages/student-report/student-report' });
            return;
          }
          wx.switchTab({ url: '/pages/volunteer/volunteer' });
        }
      });
      return;
    }
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  }
});
