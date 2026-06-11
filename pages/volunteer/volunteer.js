const { request } = require('../../utils/request');
const { fetchEntitlements, requirePermission } = require('../../utils/membership');
const { loadActiveProfileSync, refreshActiveProfile } = require('../../utils/profileHelper');
const { preparePdfFromUrl, sharePdfToWeChat, buildStudentPdfFileName } = require('../../utils/pdfExport');
const { getFlowStatus, goNextStep } = require('../../utils/applyFlow');
const { getGradientClass } = require('../../utils/volunteer');
const { formatAiContent } = require('../../utils/reportFormat');

function getLocalRiskLevel(gradientType, isAdjustable) {
  if (gradientType === '冲' && !isAdjustable) return '高';
  if (gradientType === '冲') return '中';
  if (!isAdjustable) return '中';
  return '低';
}

function getLocalRiskReason(gradientType, isAdjustable) {
  if (gradientType === '冲' && !isAdjustable) return '当前志愿为冲刺档，且未选择服从调剂，若专业分数不足，存在较高退档风险。';
  if (gradientType === '冲') return '院校往年录取位次高于当前位次，建议保留稳妥志愿兜底。';
  if (!isAdjustable) return '未选择服从调剂，达到院校投档线后仍可能因专业未录取而退档。';
  return '当前志愿结构相对稳妥，仍需以考试院和高校官方信息为准。';
}

function normalizeRisk(risk) {
  return {
    ...risk,
    chong: risk.count ? risk.count['冲'] : risk.chong || 0,
    wen: risk.count ? risk.count['稳'] : risk.wen || 0,
    bao: risk.count ? risk.count['保'] : risk.bao || 0,
    dian: risk.count ? risk.count['垫'] : risk.dian || 0
  };
}

function normalizePlan(items) {
  return items.map((item, index) => ({
    ...item,
    id: `${item.school_id}-${item.major_id}-${index}`,
    sortOrder: item.sort_order,
    gradientType: item.gradient_type,
    gradientClass: getGradientClass(item.gradient_type || item.gradientType),
    schoolId: item.school_id,
    schoolName: item.school_name,
    schoolCode: item.school_code,
    majorId: item.major_id,
    majorName: item.major_name,
    majorCode: item.major_code,
    majorType: item.major_type,
    schoolType: item.school_type,
    isAdjustable: item.is_adjustable,
    riskLevel: item.risk_level,
    riskReason: item.risk_reason
  }));
}

function toApiItem(item, index) {
  return {
    sort_order: index + 1,
    gradient_type: item.gradientType,
    school_id: item.schoolId,
    school_name: item.schoolName,
    school_code: item.schoolCode,
    major_id: item.majorId,
    major_name: item.majorName,
    major_code: item.majorCode,
    city: item.city,
    school_type: item.schoolType,
    tuition: item.tuition,
    duration: item.duration,
    is_adjustable: item.isAdjustable,
    risk_level: item.riskLevel,
    risk_reason: item.riskReason
  };
}

const PLAN_STYLE_OPTIONS = [
  { value: 'balanced', label: '均衡方案', desc: '冲2 稳5 保2' },
  { value: 'aggressive', label: '激进冲院校', desc: '冲3 稳4 保2' },
  { value: 'conservative', label: '保守稳上岸', desc: '冲1 稳5 保3' }
];

Page({
  data: {
    profile: {},
    personality: {},
    plan: [],
    riskResult: null,
    riskClass: 'risk-low',
    loading: false,
    aiExplain: '',
    aiLoading: false,
    planStyle: 'balanced',
    planStyleOptions: PLAN_STYLE_OPTIONS,
    strategyMeta: null,
    provinceRule: null,
    pdfReady: false,
    pdfFileName: ''
  },
  onShow() {
    const savedStyle = wx.getStorageSync('volunteerPlanStyle') || 'balanced';
    this.setData({ planStyle: savedStyle });
    refreshActiveProfile().then((profile) => {
      const resolvedProfile = profile || loadActiveProfileSync();
      this.setData({ profile: resolvedProfile });
      this.loadProvinceRule(resolvedProfile);
      this.consumePendingPlanAppend();
    });
    let personality = wx.getStorageSync('personalityResult') || null;
    if (personality) {
      const { migrateLegacyResult } = require('../../utils/personality');
      personality = migrateLegacyResult(personality);
      const studentAiReport = wx.getStorageSync('studentAiReport') || '';
      const aiCareerReport = studentAiReport || wx.getStorageSync('personalityAiCareerReport') || personality.aiCareerReport || '';
      if (aiCareerReport) personality = { ...personality, aiCareerReport };
    }
    if (!personality) {
      const profile = this.data.profile || loadActiveProfileSync();
      const flow = getFlowStatus(profile);
      wx.showModal({
        title: '请先完成前置流程',
        content: `当前进度 ${flow.completedCount}/${flow.totalCount}。建议先完成：${flow.currentStep.title}，再生成志愿方案。`,
        confirmText: '继续流程',
        cancelText: '知道了',
        success: (res) => {
          if (res.confirm) goNextStep(profile);
        }
      });
      return;
    }
    this.setData({ personality });
    const currentPlan = wx.getStorageSync('currentPlan') || [];
    if (currentPlan.length) {
      const plan = currentPlan.map((item) => ({
        ...item,
        gradientClass: item.gradientClass || getGradientClass(item.gradientType)
      }));
      this.setData({ plan, aiExplain: formatAiContent(wx.getStorageSync('currentAiExplain') || '') });
    }
    fetchEntitlements();
  },
  consumePendingPlanAppend() {
    const pending = wx.getStorageSync('pendingPlanAppend');
    if (!pending) return;
    wx.removeStorageSync('pendingPlanAppend');
    this.appendPlanItem(pending);
  },
  appendPlanItem(item) {
    const plan = [...this.data.plan];
    plan.push({
      ...item,
      id: `${item.schoolId}-${item.majorId}-${Date.now()}`,
      sortOrder: plan.length + 1,
      gradientClass: item.gradientClass || getGradientClass(item.gradientType),
      personalityMatched: false
    });
    this.setData({ plan, riskResult: null, aiExplain: '' });
    wx.setStorageSync('currentPlan', plan);
    wx.removeStorageSync('currentAiExplain');
    wx.showToast({ title: '已加入志愿方案', icon: 'success' });
  },
  removePlanItem(event) {
    const index = event.currentTarget.dataset.index;
    const plan = [...this.data.plan];
    plan.splice(index, 1);
    this.setData({ plan, riskResult: null, aiExplain: '' });
    wx.setStorageSync('currentPlan', plan);
    wx.removeStorageSync('currentAiExplain');
  },
  loadProvinceRule(profile) {
    const current = profile || this.data.profile || {};
    if (!current.province) {
      this.setData({ provinceRule: null });
      return;
    }
    request({
      url: '/api/province-rules/resolve',
      data: {
        province: current.province,
        batch: current.targetBatch || ''
      }
    })
      .then((res) => {
        this.setData({ provinceRule: res || null });
      })
      .catch(() => {
        this.setData({ provinceRule: null });
      });
  },
  ensureProfile() {
    const { profile } = this.data;
    if (!profile.province || !profile.subjectCombination || !profile.score || !profile.rank || !profile.targetBatch) {
      wx.showModal({
        title: '请先完善信息',
        content: '智能生成志愿需要高考省份、选科组合、分数、位次和目标批次。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
        }
      });
      return false;
    }
    return true;
  },
  clearAiExplain() {
    this.setData({ aiExplain: '' });
    wx.removeStorageSync('currentAiExplain');
  },
  onPlanStyleChange(event) {
    const planStyle = event.currentTarget.dataset.style;
    this.setData({ planStyle });
    wx.setStorageSync('volunteerPlanStyle', planStyle);
  },
  generatePlan() {
    if (!this.ensureProfile()) return;
    requirePermission('smart_recommend', '智能志愿推荐', { consume: true }).then((allowed) => {
      if (!allowed) return;
      this.doGeneratePlan();
    });
  },
  doGeneratePlan() {
    const profile = this.data.profile;
    this.setData({ loading: true });
    request({
      url: '/api/recommend',
      method: 'POST',
      data: {
        province: profile.province,
        batch: profile.targetBatch,
        score: Number(profile.score),
        rank: Number(profile.rank),
        subject_combination: profile.subjectCombination,
        major_types: (this.data.personality && this.data.personality.majorTypes) || [],
        accept_adjustment: true,
        plan_style: this.data.planStyle || 'balanced',
        volunteer_count: 0
      }
    })
      .then((res) => {
        const personality = this.data.personality || {};
        const preferredTypes = personality.majorTypes || [];
        const plan = normalizePlan(res.items || []).map((item) => ({
          ...item,
          personalityMatched: preferredTypes.includes(item.majorType),
          admissionProbability: item.admission_probability || ''
        }));
        const riskResult = normalizeRisk(res.risk || { level: '低', count: {}, warnings: [] });
        const riskClass = riskResult.level === '高' ? 'risk-high' : riskResult.level === '中' ? 'risk-mid' : 'risk-low';
        const strategyMeta = res.strategy || null;
        const provinceRule = (strategyMeta && strategyMeta.volunteer_rule) || this.data.provinceRule;
        const targetCount = provinceRule && (provinceRule.total_slots || provinceRule.school_count);
        const toastTitle = targetCount
          ? `已生成 ${plan.length}/${targetCount} 个志愿`
          : `已生成 ${plan.length} 个志愿`;
        this.setData({ plan, riskResult, riskClass, aiExplain: '', strategyMeta, provinceRule });
        wx.setStorageSync('currentPlan', plan);
        wx.setStorageSync('currentRiskResult', riskResult);
        wx.removeStorageSync('currentAiExplain');
        wx.showToast({ title: toastTitle, icon: 'success' });
      })
      .catch(() => {
        wx.showToast({ title: '推荐接口连接失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },
  inspectRisk() {
    requirePermission('risk_inspect', '志愿风险检测', { consume: true }).then((allowed) => {
      if (!allowed) return;
      this.doInspectRisk();
    });
  },
  doInspectRisk() {
    const items = this.data.plan.map(toApiItem);
    request({ url: '/api/risk-inspect', method: 'POST', data: { items } })
      .then((res) => {
        const riskResult = normalizeRisk(res);
        const riskClass = riskResult.level === '高' ? 'risk-high' : riskResult.level === '中' ? 'risk-mid' : 'risk-low';
        this.setData({ riskResult, riskClass, aiExplain: '' });
        wx.setStorageSync('currentRiskResult', riskResult);
        wx.removeStorageSync('currentAiExplain');
      })
      .catch(() => {
        wx.showToast({ title: '风险排查接口连接失败', icon: 'none' });
      });
  },
  toggleAdjust(event) {
    const index = event.currentTarget.dataset.index;
    const checked = event.detail.value;
    if (!checked) {
      wx.showModal({
        title: '请确认是否不服从调剂',
        content: '不服从专业调剂可能导致达到院校投档线后仍被退档。若该批次后续志愿机会有限，可能影响最终录取结果。请确认您已了解相关风险。',
        cancelText: '取消',
        confirmText: '确认不服从',
        success: (res) => {
          if (res.confirm) {
            this.updateAdjust(index, checked);
          }
        }
      });
      return;
    }
    this.updateAdjust(index, checked);
  },
  updateAdjust(index, checked) {
    const plan = [...this.data.plan];
    plan[index].isAdjustable = checked;
    plan[index].riskLevel = getLocalRiskLevel(plan[index].gradientType, checked);
    plan[index].riskReason = getLocalRiskReason(plan[index].gradientType, checked);
    this.setData({ plan, riskResult: null, aiExplain: '' });
    wx.setStorageSync('currentPlan', plan);
    wx.removeStorageSync('currentAiExplain');
  },
  saveDraft() {
    requirePermission('draft_save', '志愿草稿保存', { consume: true }).then((allowed) => {
      if (!allowed) return;
      this.doSaveDraft();
    });
  },
  doSaveDraft() {
    if (!this.data.plan.length) return;
    const profile = this.data.profile;
    if (!profile.studentId) {
      wx.showModal({
        title: '请先保存学生档案',
        content: '保存草稿需要先将学生档案写入数据库。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
        }
      });
      return;
    }
    const localDrafts = wx.getStorageSync('drafts') || [];
    const currentDraftId = wx.getStorageSync('currentDraftId');
    const draftName = wx.getStorageSync('currentDraftName') || `志愿方案${localDrafts.length + 1}`;
    const items = this.data.plan.map(toApiItem);
    const payload = {
      student_id: Number(profile.studentId),
      draft_name: draftName,
      province: profile.province,
      year: new Date().getFullYear(),
      batch: profile.targetBatch,
      score: Number(profile.score),
      rank: Number(profile.rank),
      risk_level: this.data.riskResult ? this.data.riskResult.level : '未排查',
      ai_explain: this.data.aiExplain,
      items
    };
    request({
      url: currentDraftId ? `/api/drafts/${currentDraftId}` : '/api/drafts',
      method: currentDraftId ? 'PUT' : 'POST',
      data: payload
    })
      .then((res) => {
        const risk = this.data.riskResult || { level: '未排查', chong: 0, wen: 0, bao: 0, dian: 0 };
        const savedId = res.draft_id || currentDraftId || `D${Date.now()}`;
        if (!currentDraftId) {
          localDrafts.unshift({ id: savedId, name: draftName, profile, plan: this.data.plan, risk, aiExplain: this.data.aiExplain, createdAt: new Date().toLocaleString() });
          wx.setStorageSync('drafts', localDrafts);
        }
        wx.setStorageSync('currentDraftId', savedId);
        wx.setStorageSync('currentDraftName', draftName);
        wx.showToast({ title: currentDraftId ? '草稿已更新' : '已保存草稿', icon: 'success' });
      })
      .catch(() => {
        wx.showToast({ title: '后端保存失败，已保存在本地', icon: 'none' });
        const risk = this.data.riskResult || { level: '未排查', chong: 0, wen: 0, bao: 0, dian: 0 };
        localDrafts.unshift({ id: `D${Date.now()}`, name: draftName, profile, plan: this.data.plan, risk, aiExplain: this.data.aiExplain, createdAt: new Date().toLocaleString() });
        wx.setStorageSync('drafts', localDrafts);
      });
  },

  explainPlan() {
    requirePermission('ai_plan_explain', 'AI 志愿方案解读', { consume: true }).then((allowed) => {
      if (!allowed) return;
      this.doExplainPlan();
    });
  },
  doExplainPlan() {
    if (!this.data.plan.length) {
      wx.showToast({ title: '请先生成志愿方案', icon: 'none' });
      return;
    }
    this.setData({ aiLoading: true });
    request({
      url: '/api/ai/plan-explain',
      method: 'POST',
      data: {
        profile: this.data.profile,
        personality: this.data.personality,
        risk: this.data.riskResult || {},
        items: this.data.plan.map(toApiItem)
      }
    })
      .then((res) => {
        const aiExplain = formatAiContent(res.explain || '');
        this.setData({ aiExplain });
        wx.setStorageSync('currentAiExplain', aiExplain);
        wx.showToast({ title: 'AI 解读已生成', icon: 'success' });
      })
      .catch((error) => {
        wx.showToast({ title: error.message || 'AI 解读失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ aiLoading: false });
      });
  },
  copyAiExplain() {
    if (!this.data.aiExplain) {
      wx.showToast({ title: '暂无可复制内容', icon: 'none' });
      return;
    }
    wx.setClipboardData({
      data: this.data.aiExplain,
      success: () => {
        wx.showToast({ title: '已复制解读', icon: 'success' });
      }
    });
  },
  generatePlanPdf() {
    requirePermission('pdf_export', 'PDF 志愿表导出', { consume: true }).then((allowed) => {
      if (!allowed) return;
      this.doGeneratePlanPdf();
    });
  },
  doGeneratePlanPdf() {
    const profile = this.data.profile;
    const currentDraftId = wx.getStorageSync('currentDraftId');
    if (!this.data.plan.length) return;
    if (!profile.studentId) {
      wx.showToast({ title: '请先保存学生档案', icon: 'none' });
      return;
    }
    if (!currentDraftId) {
      wx.showModal({
        title: '请先保存草稿',
        content: 'PDF 导出需要先保存草稿。',
        confirmText: '知道了'
      });
      return;
    }
    const fileName = buildStudentPdfFileName(profile, '填报志愿');
    const pdfUrl = `/api/drafts/${currentDraftId}/pdf?student_id=${profile.studentId}`;
    preparePdfFromUrl(pdfUrl, { fileName })
      .then(({ filePath, fileName: savedName }) => {
        this._pdfFilePath = filePath;
        this._pdfFileName = savedName;
        this.setData({ pdfReady: true, pdfFileName: savedName });
        const records = wx.getStorageSync('exportRecords') || [];
        records.unshift({
          id: Date.now(),
          draftId: currentDraftId,
          time: new Date().toLocaleString(),
          count: this.data.plan.length,
          type: 'pdf'
        });
        wx.setStorageSync('exportRecords', records);
        wx.showToast({ title: '已生成，请点②发送', icon: 'success' });
      })
      .catch((error) => {
        wx.showToast({ title: error.message || 'PDF 生成失败', icon: 'none' });
      });
  },
  sendPlanPdfToWeChat() {
    if (!this._pdfFilePath || !this._pdfFileName) {
      wx.showToast({ title: '请先点①生成PDF', icon: 'none' });
      return;
    }
    sharePdfToWeChat(this._pdfFilePath, this._pdfFileName)
      .then(() => wx.showToast({ title: '请选择文件传输助手', icon: 'none' }))
      .catch((error) => wx.showToast({ title: error.message || '发送失败', icon: 'none' }));
  },
  goCompare() {
    wx.navigateTo({ url: '/pages/compare/compare' });
  }
});
