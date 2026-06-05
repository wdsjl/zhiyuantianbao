const { request } = require('../../utils/request');
const { loadActiveProfileSync } = require('../../utils/profileHelper');
const { requirePermission } = require('../../utils/membership');

function normalizeServerDraft(draft) {
  const count = { chong: 0, wen: 0, bao: 0, dian: 0 };
  const plan = (draft.items || []).map((item) => {
    if (item.gradient_type === '冲') count.chong += 1;
    if (item.gradient_type === '稳') count.wen += 1;
    if (item.gradient_type === '保') count.bao += 1;
    if (item.gradient_type === '垫') count.dian += 1;
    return {
      schoolName: item.school_name,
      city: item.city,
      schoolType: item.school_type,
      isAdjustable: Boolean(item.is_adjustable),
      isDoubleFirstClass: Boolean(item.is_double_first_class)
    };
  });
  return {
    id: draft.draft_id,
    name: draft.draft_name,
    createdAt: draft.created_at,
    plan,
    risk: {
      level: draft.risk_level || '未排查',
      chong: count.chong,
      wen: count.wen,
      bao: count.bao,
      dian: count.dian
    }
  };
}

function enrichDraft(draft) {
  const adjustCount = draft.plan.filter((item) => item.isAdjustable).length;
  const publicCount = draft.plan.filter((item) => item.schoolType === '公办' || item.schoolType === '综合').length;
  const doubleFirstCount = draft.plan.filter((item) => item.isDoubleFirstClass).length;
  const cities = Array.from(new Set(draft.plan.map((item) => item.city).filter(Boolean))).join('、') || '--';
  return { ...draft, adjustCount, publicCount, doubleFirstCount, cities };
}

Page({
  data: {
    drafts: [],
    loading: false
  },
  onShow() {
    requirePermission('school_compare', '院校对比', { consume: false }).then(() => {
      this.fetchDrafts();
    });
  },
  fetchDrafts() {
    const profile = loadActiveProfileSync();
    this.setData({ loading: true });
    if (!profile.studentId) {
      const drafts = (wx.getStorageSync('drafts') || []).slice(0, 3).map(enrichDraft);
      this.setData({ drafts, loading: false });
      return;
    }
    request({ url: '/api/drafts', data: { student_id: Number(profile.studentId) } })
      .then((res) => {
        const serverDrafts = (res.list || []).map(normalizeServerDraft).map(enrichDraft).slice(0, 3);
        const localDrafts = (wx.getStorageSync('drafts') || []).map(enrichDraft).slice(0, 3);
        this.setData({ drafts: serverDrafts.length ? serverDrafts : localDrafts });
      })
      .catch(() => {
        const drafts = (wx.getStorageSync('drafts') || []).slice(0, 3).map(enrichDraft);
        this.setData({ drafts });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  }
});
