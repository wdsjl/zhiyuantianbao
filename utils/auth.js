const { request } = require('./request');

function isTempOpenid(openid) {
  return !openid || /^(dev_|local_|test_)/.test(openid);
}

function mergeLoginProfile(loginRes) {
  if (!loginRes || !loginRes.profile) return;
  const oldProfile = wx.getStorageSync('studentProfile') || {};
  const profile = {
    ...oldProfile,
    openid: loginRes.openid,
    userId: loginRes.user_id,
    studentId: loginRes.profile.student_id || oldProfile.studentId,
    name: loginRes.profile.name || oldProfile.name,
    phone: loginRes.profile.phone || oldProfile.phone,
    province: loginRes.profile.province || oldProfile.province,
    city: loginRes.profile.city || oldProfile.city,
    school: loginRes.profile.school_name || oldProfile.school,
    grade: loginRes.profile.grade || oldProfile.grade,
    className: loginRes.profile.class_name || oldProfile.className,
    subjectCombination: loginRes.profile.subject_combination || oldProfile.subjectCombination,
    score: loginRes.profile.score || oldProfile.score,
    rank: loginRes.profile.rank || oldProfile.rank,
    targetBatch: loginRes.profile.target_batch || oldProfile.targetBatch
  };
  wx.setStorageSync('studentProfile', profile);
}

function syncProfileToServer(profile, openid) {
  if (!profile || !profile.province || !profile.score || !profile.rank) {
    return Promise.resolve(null);
  }
  return request({
    url: '/api/profile',
    method: 'POST',
    data: {
      openid,
      phone: profile.phone,
      role: profile.role || '学生',
      name: profile.name,
      province: profile.province,
      city: profile.city,
      exam_year: new Date().getFullYear(),
      exam_type: '普通类',
      subject_combination: profile.subjectCombination,
      score: Number(profile.score),
      rank: Number(profile.rank),
      target_batch: profile.targetBatch
    }
  }).then((res) => {
    const updated = {
      ...profile,
      openid: res.openid || openid,
      userId: res.user_id,
      studentId: res.student_id
    };
    wx.setStorageSync('studentProfile', updated);
    const loginUser = wx.getStorageSync('loginUser') || {};
    wx.setStorageSync('loginUser', {
      ...loginUser,
      openid: updated.openid,
      user_id: updated.userId,
      has_profile: true
    });
    return updated;
  });
}

function ensureWechatLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        const code = res.code || '';
        if (!code) {
          reject(new Error('微信登录失败，请关闭小程序后重试'));
          return;
        }
        const profile = wx.getStorageSync('studentProfile') || {};
        request({
          url: '/api/auth/login',
          method: 'POST',
          data: {
            code,
            phone: profile.phone || '',
            name: profile.name || '',
            role: profile.role || wx.getStorageSync('currentRole') || 'student'
          }
        })
          .then((loginRes) => {
            if (isTempOpenid(loginRes.openid)) {
              reject(new Error(
                '服务端未配置微信 AppSecret。请在服务器 ecosystem.secrets.js 填写 WECHAT_SECRET 后执行 pm2 restart zhiyuan-backend'
              ));
              return null;
            }
            wx.setStorageSync('loginUser', loginRes);
            mergeLoginProfile(loginRes);
            const latestProfile = wx.getStorageSync('studentProfile') || profile;
            if (isTempOpenid(latestProfile.openid)) {
              latestProfile.openid = loginRes.openid;
              latestProfile.userId = loginRes.user_id;
              wx.setStorageSync('studentProfile', latestProfile);
            }
            return syncProfileToServer(latestProfile, loginRes.openid).then(() => loginRes);
          })
          .then((loginRes) => {
            if (loginRes) resolve(loginRes);
          })
          .catch(reject);
      },
      fail() {
        reject(new Error('微信登录失败，请检查网络后重试'));
      }
    });
  });
}

function login() {
  return new Promise((resolve) => {
    wx.login({
      success(res) {
        const code = res.code || '';
        request({
          url: '/api/auth/login',
          method: 'POST',
          data: {
            code,
            role: wx.getStorageSync('currentRole') || 'student'
          }
        })
          .then((loginRes) => {
            wx.setStorageSync('loginUser', loginRes);
            mergeLoginProfile(loginRes);
            resolve(loginRes);
          })
          .catch(() => {
            const fallback = {
              user_id: '',
              openid: wx.getStorageSync('devOpenid') || `dev_${Date.now()}`,
              has_profile: false
            };
            wx.setStorageSync('devOpenid', fallback.openid);
            wx.setStorageSync('loginUser', fallback);
            resolve(fallback);
          });
      },
      fail() {
        const fallback = {
          user_id: '',
          openid: wx.getStorageSync('devOpenid') || `dev_${Date.now()}`,
          has_profile: false
        };
        wx.setStorageSync('devOpenid', fallback.openid);
        wx.setStorageSync('loginUser', fallback);
        resolve(fallback);
      }
    });
  });
}

module.exports = {
  login,
  ensureWechatLogin,
  isTempOpenid
};
