function normalizeInviteCode(code) {
  return String(code || '').trim().toUpperCase();
}

function captureInviteFromLaunch(options) {
  options = options || {};
  let code = '';
  const query = options.query || {};
  if (query.invite || query.agent || query.agent_id || query['达人ID']) {
    code = query.invite || query.agent || query.agent_id || query['达人ID'];
  } else if (options.scene) {
    try {
      code = decodeURIComponent(options.scene);
    } catch (error) {
      code = options.scene;
    }
  }
  code = normalizeInviteCode(code);
  if (code) {
    try {
      wx.setStorageSync('pendingInviteCode', code);
    } catch (error) {
      // 开发者工具偶发 storage 失败时忽略，不影响主流程
    }
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
