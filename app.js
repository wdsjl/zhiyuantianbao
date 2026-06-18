const { login } = require('./utils/auth');
const { captureInviteFromLaunch } = require('./utils/referral');

function safeGetStorage(key, fallback) {
  try {
    const value = wx.getStorageSync(key);
    return value === '' || value === undefined || value === null ? fallback : value;
  } catch (error) {
    return fallback;
  }
}

function safeSetStorage(key, value) {
  try {
    wx.setStorageSync(key, value);
    return true;
  } catch (error) {
    return false;
  }
}

App({
  globalData: {
    userInfo: null,
    currentRole: '',
    studentProfile: null,
    loginUser: null
  },
  onLaunch(options) {
    captureInviteFromLaunch(options);
    if (!safeGetStorage('deviceId', '')) {
      safeSetStorage('deviceId', `d_${Date.now()}_${Math.floor(Math.random() * 100000)}`);
    }
    const userInfo = safeGetStorage('userInfo', null);
    const currentRole = safeGetStorage('currentRole', '');
    const studentProfile = safeGetStorage('studentProfile', null);
    const loginUser = safeGetStorage('loginUser', null);
    this.globalData.userInfo = userInfo;
    this.globalData.currentRole = currentRole;
    this.globalData.studentProfile = studentProfile;
    this.globalData.loginUser = loginUser;

    login().then((res) => {
      this.globalData.loginUser = res;
      this.globalData.studentProfile = safeGetStorage('studentProfile', null);
    }).catch(() => {});
  }
});
