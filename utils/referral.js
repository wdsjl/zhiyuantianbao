function normalizeInviteCode(code) {
  return String(code || '').trim().toUpperCase();
}

function captureInviteFromLaunch(options) {
  options = options || {};
  let code = '';
  if (options.query && options.query.invite) {
    code = options.query.invite;
  } else if (options.scene) {
    try {
      code = decodeURIComponent(options.scene);
    } catch (error) {
      code = options.scene;
    }
  }
  code = normalizeInviteCode(code);
  if (code) {
    wx.setStorageSync('pendingInviteCode', code);
  }
}

function getPendingInviteCode() {
  return normalizeInviteCode(wx.getStorageSync('pendingInviteCode') || '');
}

function clearPendingInviteCode() {
  wx.removeStorageSync('pendingInviteCode');
}

module.exports = {
  normalizeInviteCode,
  captureInviteFromLaunch,
  getPendingInviteCode,
  clearPendingInviteCode
};
