const { login } = require('./utils/auth');
const { captureInviteFromLaunch } = require('./utils/referral');

App({
  globalData: {
    userInfo: null,
    currentRole: '',
    studentProfile: null,
    loginUser: null
  },
  onLaunch(options) {
    captureInviteFromLaunch(options);
    if (!wx.getStorageSync('deviceId')) {
      wx.setStorageSync('deviceId', `d_${Date.now()}_${Math.floor(Math.random() * 100000)}`);
    }
    const userInfo = wx.getStorageSync('userInfo') || null;
    const currentRole = wx.getStorageSync('currentRole') || '';
    const studentProfile = wx.getStorageSync('studentProfile') || null;
    const loginUser = wx.getStorageSync('loginUser') || null;
    this.globalData.userInfo = userInfo;
    this.globalData.currentRole = currentRole;
    this.globalData.studentProfile = studentProfile;
    this.globalData.loginUser = loginUser;

    login().then((res) => {
      this.globalData.loginUser = res;
      const latestProfile = wx.getStorageSync('studentProfile') || null;
      this.globalData.studentProfile = latestProfile;
    });
  }
});
