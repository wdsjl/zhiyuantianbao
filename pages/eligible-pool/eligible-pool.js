const { request } = require('../../utils/request');
const { loadActiveProfileSync, refreshActiveProfile } = require('../../utils/profileHelper');
const { buildProfileSnapshot } = require('../../utils/profileSnapshot');
const { buildRecommendPayload } = require('../../utils/recommendPayload');
const { getGradientClass } = require('../../utils/volunteer');
const { isArtSportsActive } = require('../../utils/henanArtSports');

const GRADIENT_TABS = [
  { value: '', label: '全部' },
  { value: '冲', label: '冲' },
  { value: '稳', label: '稳' },
  { value: '保', label: '保' },
  { value: '垫', label: '垫' }
];

function normalizeSummary(summary) {
  const raw = summary || {};
  return {
    total: raw.total || 0,
    rush: raw['冲'] || raw.rush || 0,
    steady: raw['稳'] || raw.steady || 0,
    safe: raw['保'] || raw.safe || 0,
    cushion: raw['垫'] || raw.cushion || 0
  };
}

const ART_SPORTS_GRADIENT_TABS = [
  { value: '', label: '全部' },
  { value: '冲', label: '冲' },
  { value: '稳', label: '稳' },
  { value: '保', label: '保' }
];

Page({
  data: {
    profile: {},
    items: [],
    summary: { total: 0, rush: 0, steady: 0, safe: 0, cushion: 0 },
    strategy: null,
    gradientTabs: GRADIENT_TABS,
    activeGradient: '',
    keyword: '',
    page: 1,
    pageSize: 50,
    total: 0,
    loading: false,
    hasMore: false,
    userRank: '',
    artSportsMode: false,
    compositeScore: ''
  },
  onShow() {
    refreshActiveProfile().then((profile) => {
      const resolved = profile || loadActiveProfileSync();
      const artSportsMode = isArtSportsActive(resolved);
      this.setData({
        profile: resolved,
        artSportsMode,
        gradientTabs: artSportsMode ? ART_SPORTS_GRADIENT_TABS : GRADIENT_TABS
      });
      if (!resolved.score || !resolved.province || !resolved.targetBatch) {
        wx.showModal({
          title: '请先完善档案',
          content: artSportsMode
            ? '艺体检索需要文化课分数、专业统考分、省份和批次。'
            : '检索可报院校需要分数、位次、省份和批次。',
          confirmText: '去完善',
          success: (res) => {
            if (res.confirm) {
              const track = resolved.examType === '体育类' ? 'sports' : (resolved.examType === '艺术类' ? 'art' : '');
              wx.navigateTo({ url: track ? `/pages/profile/profile?track=${track}` : '/pages/profile/profile' });
            }
          }
        });
        return;
      }
      if (artSportsMode && !resolved.professionalScore && !resolved.professional_score) {
        wx.showModal({
          title: '请填写专业统考分',
          content: '河南艺体考生须填写专业统考分，才能按综合分对标检索院校。',
          confirmText: '去完善',
          success: (res) => {
            if (res.confirm) {
              const track = resolved.examType === '体育类' ? 'sports' : 'art';
              wx.navigateTo({ url: `/pages/profile/profile?track=${track}` });
            }
          }
        });
        return;
      }
      if (!artSportsMode && !resolved.rank) {
        wx.showModal({
          title: '请先完善档案',
          content: '检索可报院校需要分数、位次、省份和批次。',
          confirmText: '去完善',
          success: (res) => {
            if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
          }
        });
        return;
      }
      const snapshot = wx.getStorageSync('eligiblePoolSnapshot') || '';
      const currentSnapshot = buildProfileSnapshot(resolved);
      if (snapshot !== currentSnapshot) {
        this.setData({ page: 1, items: [] });
      }
      this.fetchPool(true);
    });
  },
  onKeywordInput(event) {
    this.setData({ keyword: event.detail.value });
  },
  onSearch() {
    this.setData({ page: 1, items: [] });
    this.fetchPool(true);
  },
  onGradientChange(event) {
    const activeGradient = event.currentTarget.dataset.value || '';
    this.setData({ activeGradient, page: 1, items: [] });
    this.fetchPool(true);
  },
  fetchPool(reset) {
    const { profile, page, pageSize, activeGradient, keyword } = this.data;
    if (!profile.province) return;
    this.setData({ loading: true });
    const payload = {
      ...buildRecommendPayload(profile, { hardFilterMajorTypes: false }),
      gradient: activeGradient,
      keyword: keyword || '',
      page,
      page_size: pageSize
    };
    request({ url: '/api/eligible-pool', method: 'POST', data: payload })
      .then((res) => {
        const mapped = (res.items || []).map((item) => ({
          ...item,
          gradientClass: getGradientClass(item.gradient_type)
        }));
        const items = reset ? mapped : [...this.data.items, ...mapped];
        wx.setStorageSync('eligiblePoolSnapshot', buildProfileSnapshot(profile));
        wx.setStorageSync('eligiblePoolSummary', res.summary || {});
        this.setData({
          items,
          summary: normalizeSummary(res.summary),
          strategy: res.strategy || null,
          total: res.total || 0,
          userRank: res.user_rank || profile.rank,
          compositeScore: res.composite_score || (res.strategy && res.strategy.composite_score) || '',
          hasMore: items.length < (res.total || 0),
          page: page + 1
        });
      })
      .catch((error) => {
        wx.showToast({ title: error.message || '检索失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },
  loadMore() {
    if (this.data.loading || !this.data.hasMore) return;
    this.fetchPool(false);
  },
  goPersonality() {
    wx.navigateTo({ url: '/pages/personality/personality' });
  },
  goPreferences() {
    wx.navigateTo({ url: '/pages/student-report/student-report' });
  },
  goVolunteer() {
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  },
  openSchool(event) {
    const schoolId = event.currentTarget.dataset.schoolId;
    if (!schoolId || this.data.artSportsMode) return;
    wx.navigateTo({ url: `/pages/school-detail/school-detail?id=${schoolId}` });
  }
});
