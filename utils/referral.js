function normalizeInviteCode(code) {
  return String(code || '').trim().toUpperCase();
}

function isValidInviteCode(code) {
  const normalized = normalizeInviteCode(code);
  return /^[A-Z0-9]{4,20}$/.test(normalized);
}

function cleanupInvalidInviteCode() {
  try {
    const raw = wx.getStorageSync('pendingInviteCode');
    if (!raw) return;
    if (!isValidInviteCode(raw)) {
      wx.removeStorageSync('pendingInviteCode');
    }
  } catch (error) {
    // 开发者工具偶发 storage 失败时忽略
  }
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
  isValidInviteCode,
  cleanupInvalidInviteCode,
  captureInviteFromLaunch,
  getPendingInviteCode,
  clearPendingInviteCode
};
