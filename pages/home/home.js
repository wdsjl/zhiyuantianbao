const { refreshActiveProfile } = require('../../utils/profileHelper');
const { getFlowStatus, goNextStep, navigateToStep } = require('../../utils/applyFlow');
const { captureInviteFromLaunch, getPendingInviteCode, clearPendingInviteCode } = require('../../utils/referral');
const { request } = require('../../utils/request');
const { getCurrentUserId } = require('../../utils/membership');

Page({
  data: {
    profile: {},
    personality: {},
    flow: {
      steps: [],
      completedCount: 0,
      totalCount: 5,
      progressPercent: 0,
      currentStep: { title: '完善档案', desc: '' },
      allDone: false
    }
  },
  onLoad(options) {
    captureInviteFromLaunch({ query: options || {}, scene: options && options.scene });
    this.tryBindInvite();
  },
  tryBindInvite() {
    const inviteCode = getPendingInviteCode();
    const userId = getCurrentUserId();
    if (!inviteCode || !userId) return;
    const deviceId = wx.getStorageSync('deviceId') || '';
    request({
      url: '/api/referral/bind',
      method: 'POST',
      data: {
        user_id: Number(userId),
        invite_code: inviteCode,
        device_id: deviceId
      }
    }).then((res) => {
      clearPendingInviteCode();
      if (res && res.message) {
        wx.showModal({
          title: res.reason === 'already_bound_same' ? '已绑定' : '绑定成功',
          content: res.message,
          showCancel: false
        });
      }
    }).catch((error) => {
      if (error && error.message && error.message.indexOf('已绑定其他渠道') >= 0) {
        wx.showModal({ title: '无法更换渠道', content: error.message, showCancel: false });
        clearPendingInviteCode();
      }
    });
  },
  onShow() {
    this.tryBindInvite();
    refreshActiveProfile().then((profile) => {
      const savedProfile = profile || wx.getStorageSync('studentProfile') || {};
      const personality = (() => {
        const { migrateLegacyResult } = require('../../utils/personality');
        const result = wx.getStorageSync('personalityResult') || {};
        return result.code ? migrateLegacyResult(result) : result;
      })();
      const flow = getFlowStatus(savedProfile);
      this.setData({ profile: savedProfile, personality, flow });
    });
  },
  continueFlow() {
    goNextStep(this.data.profile);
  },
  openStep(event) {
    const key = event.currentTarget.dataset.key;
    navigateToStep(key);
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' });
  },
  goPersonality() {
    wx.navigateTo({ url: '/pages/personality/personality' });
  },
  goEligiblePool() {
    const profile = this.data.profile || {};
    if (!profile.score || !profile.rank) {
      wx.showModal({
        title: '请先完善档案',
        content: '检索可报院校需要分数和位次。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) this.goProfile();
        }
      });
      return;
    }
    wx.navigateTo({ url: '/pages/eligible-pool/eligible-pool' });
  },
  goVolunteer() {
    const flow = getFlowStatus(this.data.profile);
    if (!flow.checks.profile) {
      wx.showModal({
        title: '请先完善档案',
        content: '智能填报需要分数、位次、选科和批次。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) this.goProfile();
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
    const { goMembershipPage } = require('../../utils/membership');
    goMembershipPage();
  },
  goStudentReport() {
    wx.navigateTo({ url: '/pages/student-report/student-report' });
  }
});
