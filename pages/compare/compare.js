Page({
  data: {
    drafts: []
  },
  onShow() {
    const drafts = (wx.getStorageSync('drafts') || []).slice(0, 3).map((draft) => {
      const adjustCount = draft.plan.filter((item) => item.isAdjustable).length;
      const doubleFirstCount = draft.plan.filter((item) => item.tags && item.tags.includes('双一流')).length;
      const cities = Array.from(new Set(draft.plan.map((item) => item.city))).join('、') || '--';
      return { ...draft, adjustCount, doubleFirstCount, cities };
    });
    this.setData({ drafts });
  }
});
