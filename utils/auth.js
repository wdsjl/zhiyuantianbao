const { request } = require('./request');

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
            if (loginRes.profile) {
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
  login
};
