const { request } = require('../../utils/request');
const { loadActiveProfileSync } = require('../../utils/profileHelper');
const { openPdfFromUrl, buildStudentPdfFileName } = require('../../utils/pdfExport');

function normalizeServerDraft(draft) {
  const count = { chong: 0, wen: 0, bao: 0, dian: 0 };
  const plan = (draft.items || []).map((item) => {
    if (item.gradient_type === '冲') count.chong += 1;
    if (item.gradient_type === '稳') count.wen += 1;
    if (item.gradient_type === '保') count.bao += 1;
    if (item.gradient_type === '垫') count.dian += 1;
    return {
      id: item.item_id,
      sortOrder: item.sort_order,
      gradientType: item.gradient_type,
      schoolId: item.school_id,
      schoolName: item.school_name,
      schoolCode: item.school_code,
      majorId: item.major_id,
      majorName: item.major_name,
      majorCode: item.major_code,
      city: item.city,
      schoolType: item.school_type,
      tuition: item.tuition,
      duration: item.duration,
      isAdjustable: Boolean(item.is_adjustable),
      riskLevel: item.risk_level,
      riskReason: item.risk_reason
    };
  });
  return {
    id: draft.draft_id,
    name: draft.draft_name,
    createdAt: draft.created_at,
    plan,
    aiExplain: draft.ai_explain || draft.aiExplain || '',
    risk: {
      level: draft.risk_level || '未排查',
      chong: count.chong,
      wen: count.wen,
      bao: count.bao,
      dian: count.dian
    }
  };
}

Page({
  data: {
    drafts: [],
    loading: false
  },
  onShow() {
    this.fetchDrafts();
  },
  fetchDrafts() {
    const profile = loadActiveProfileSync();
    if (!profile.studentId) {
      this.setData({ drafts: wx.getStorageSync('drafts') || [] });
      return;
    }
    const studentId = Number(profile.studentId);
    this.setData({ loading: true });
    request({ url: '/api/drafts', data: { student_id: studentId } })
      .then((res) => {
        const serverDrafts = (res.list || []).map(normalizeServerDraft);
        this.setData({ drafts: serverDrafts.length ? serverDrafts : wx.getStorageSync('drafts') || [] });
      })
      .catch(() => {
        this.setData({ drafts: wx.getStorageSync('drafts') || [] });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },
  goVolunteer() {
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  },
  editDraft(event) {
    const draft = this.data.drafts[event.currentTarget.dataset.index];
    wx.setStorageSync('currentPlan', draft.plan);
    wx.setStorageSync('currentDraftId', draft.id);
    wx.setStorageSync('currentDraftName', draft.name);
    wx.setStorageSync('currentAiExplain', draft.aiExplain || '');
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  },
  exportDraft(event) {
    const index = event.currentTarget.dataset.index;
    const draft = this.data.drafts[index];
    const profile = loadActiveProfileSync();
    if (!profile.studentId || !draft.id) {
      wx.showToast({ title: '请先保存到后端草稿', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '导出 PDF 志愿表',
      content: '将生成 PDF 文件，内容包含学生基础信息、志愿顺序、院校专业代码、学费学制、是否服从调剂和风险提示。结果仅供参考。',
      confirmText: '导出 PDF',
      success: (res) => {
        if (!res.confirm) return;
        openPdfFromUrl(
          `/api/drafts/${draft.id}/pdf?student_id=${profile.studentId}`,
          { fileName: buildStudentPdfFileName(profile, '填报志愿') }
        )
          .then(() => {
            wx.showToast({ title: 'PDF 已打开', icon: 'success' });
          })
          .catch((error) => {
            wx.showToast({ title: error.message || 'PDF 导出失败', icon: 'none' });
          });
      }
    });
  },
  deleteDraft(event) {
    const index = event.currentTarget.dataset.index;
    const draft = this.data.drafts[index];
    const profile = loadActiveProfileSync();
    wx.showModal({
      title: '删除草稿',
      content: '删除后不可恢复，是否继续？',
      success: (res) => {
        if (!res.confirm) return;
        const removeLocal = () => {
          const drafts = [...this.data.drafts];
          drafts.splice(index, 1);
          wx.setStorageSync('drafts', drafts);
          this.setData({ drafts });
        };
        if (profile.studentId && draft.id) {
          request({ url: `/api/drafts/${draft.id}?student_id=${profile.studentId}`, method: 'DELETE' })
            .then(() => {
              removeLocal();
              wx.showToast({ title: '删除成功', icon: 'success' });
            })
            .catch(() => {
              wx.showToast({ title: '后端删除失败', icon: 'none' });
            });
          return;
        }
        removeLocal();
      }
    });
  }
});
