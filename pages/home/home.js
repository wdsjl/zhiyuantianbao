const { refreshActiveProfile } = require('../../utils/profileHelper');
const { getFlowStatus, goNextStep, navigateToStep } = require('../../utils/applyFlow');

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
  onShow() {
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
  }
});
