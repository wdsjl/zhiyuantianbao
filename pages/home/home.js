const { refreshActiveProfile } = require('../../utils/profileHelper');

Page({
  data: {
    profile: {},
    personality: {}
  },
  onShow() {
    refreshActiveProfile().then((profile) => {
      this.setData({
        profile: profile || wx.getStorageSync('studentProfile') || {},
        personality: (() => {
          const { migrateLegacyResult } = require('../../utils/personality');
          const result = wx.getStorageSync('personalityResult') || {};
          return result.code ? migrateLegacyResult(result) : result;
        })()
      });
    });
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' });
  },
  goPersonality() {
    wx.navigateTo({ url: '/pages/personality/personality' });
  },
  goVolunteer() {
    const personality = wx.getStorageSync('personalityResult');
    if (!personality) {
      wx.showModal({
        title: '请先完成性格测评',
        content: '为了更好地匹配适合你的专业方向，进入志愿填报前需要先完成一次性格测评。',
        confirmText: '去测评',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/personality/personality' });
        }
      });
      return;
    }
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  },
  goDrafts() {
    wx.navigateTo({ url: '/pages/drafts/drafts' });
  },
  goSchools() {
    wx.switchTab({ url: '/pages/schools/schools' });
  },
  goMembership() {
    wx.navigateTo({ url: '/pages/membership/membership' });
  }
});
