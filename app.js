const { login } = require('./utils/auth');

App({
  globalData: {
    userInfo: null,
    currentRole: '',
    studentProfile: null,
    loginUser: null
  },
  onLaunch() {
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
