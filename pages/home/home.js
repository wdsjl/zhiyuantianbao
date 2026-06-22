const { refreshActiveProfile } = require('../../utils/profileHelper');
const { getFlowStatus, goNextStep, navigateToStep } = require('../../utils/applyFlow');
const { captureInviteFromLaunch, getPendingInviteCode, clearPendingInviteCode, cleanupInvalidInviteCode } = require('../../utils/referral');
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
    cleanupInvalidInviteCode();
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
    cleanupInvalidInviteCode();
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
  goProfileArt() {
    wx.navigateTo({ url: '/pages/profile/profile?track=art' });
  },
  goProfileSports() {
    wx.navigateTo({ url: '/pages/profile/profile?track=sports' });
  },
  goArtZone() {
    wx.navigateTo({ url: '/pages/art-zone/art-zone' });
  },
  goSportsZone() {
    wx.navigateTo({ url: '/pages/sports-zone/sports-zone' });
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
  goEligiblePool() {
    const profile = this.data.profile || {};
    if (!profile.province || !profile.score || !profile.targetBatch) {
      wx.showModal({
        title: '请先完善档案',
        content: '检索可报院校需要分数、省份和批次。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
        }
      });
      return;
    }
    const { isArtSportsActive } = require('../../utils/henanArtSports');
    if (isArtSportsActive(profile) && !(profile.professionalScore || profile.professional_score)) {
      const track = profile.examType === '体育类' ? 'sports' : 'art';
      wx.showModal({
        title: '请填写专业统考分',
        content: '河南艺体考生须先填写专业统考分。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: `/pages/profile/profile?track=${track}` });
        }
      });
      return;
    }
    wx.navigateTo({ url: '/pages/eligible-pool/eligible-pool' });
  },
  goMembership() {
    const { goMembershipPage } = require('../../utils/membership');
    goMembershipPage();
  },
  goStudentReport() {
    wx.navigateTo({ url: '/pages/student-report/student-report' });
  }
});
