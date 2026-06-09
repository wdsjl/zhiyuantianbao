const { refreshActiveProfile } = require('../../utils/profileHelper');
const { getFlowStatus, goNextStep, navigateToStep } = require('../../utils/applyFlow');
const { captureInviteFromLaunch, getPendingInviteCode, clearPendingInviteCode } = require('../../utils/referral');
const { request } = require('../../utils/request');
const { getCurrentUserId } = require('../../utils/membership');
const { BUILD_TAG } = require('../../utils/miniappVersion');

Page({
  data: {
    buildTag: BUILD_TAG,
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
      if (!res || !res.success) return;
      const userId = getCurrentUserId();
      const scanReward = res.scan_reward || {};
      const showResult = (bonusRes) => {
        let content = res.message || '渠道绑定成功';
        const expectedBeans = (scanReward && scanReward.bonus_beans) || (bonusRes && bonusRes.bonus_beans) || 0;
        if (bonusRes && bonusRes.claimed) {
          content += `\n\n已领取达人专属 ${bonusRes.bonus_beans} 星鼎豆`;
        } else if (expectedBeans > 0 && bonusRes && bonusRes.message) {
          content += `\n\n${bonusRes.message}`;
        } else if (expectedBeans > 0) {
          content += `\n\n可领取 ${expectedBeans} 星鼎豆，请稍后在「会员」页查看余额`;
        }
        wx.showModal({
          title: res.reason === 'already_bound_same' ? '已绑定' : '绑定成功',
          content,
          showCancel: false
        });
      };
      if (!userId) {
        showResult(null);
        return;
      }
      request({
        url: '/api/referral/claim-bonus',
        method: 'POST',
        data: { user_id: Number(userId) }
      }).then(showResult).catch(() => showResult(null));
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
  goVolunteer() {
    const flow = getFlowStatus(this.data.profile);
    if (!flow.checks.personality) {
      wx.showModal({
        title: '请先完成霍兰德测评',
        content: '按推荐流程，完成测评和个性化报告后再填报志愿，结果会更准确。',
        confirmText: '继续流程',
        success: (res) => {
          if (res.confirm) this.continueFlow();
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
  },
  goPromotion() {
    wx.navigateTo({ url: '/pages/promotion/promotion' });
  }
});
