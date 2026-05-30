const { fetchEntitlements } = require('../../utils/membership');

Page({
  data: {
    profile: {},
    draftCount: 0,
    exportCount: 0,
    planName: '免费版',
    expiresAt: ''
  },
  onShow() {
    this.setData({
      profile: wx.getStorageSync('studentProfile') || {},
      draftCount: (wx.getStorageSync('drafts') || []).length,
      exportCount: (wx.getStorageSync('exportRecords') || []).length
    });
    fetchEntitlements()
      .then((res) => {
        this.setData({
          planName: res.plan ? res.plan.plan_name : '免费版',
          expiresAt: res.membership && res.membership.expires_at ? res.membership.expires_at : ''
        });
      })
      .catch(() => {});
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' });
  },
  goDrafts() {
    wx.navigateTo({ url: '/pages/drafts/drafts' });
  },
  goCompare() {
    wx.navigateTo({ url: '/pages/compare/compare' });
  },
  goMembership() {
    wx.navigateTo({ url: '/pages/membership/membership' });
  }
});
