const { request } = require('./request');

const PERMISSION_LABELS = {
  smart_recommend: '智能志愿推荐',
  risk_inspect: '志愿风险检测',
  ai_plan_explain: 'AI 志愿方案解读',
  draft_save: '志愿草稿保存',
  pdf_export: 'PDF 志愿表导出',
  school_compare: '院校对比',
  score_full_history: '完整历年分数线和位次',
  personality_deep: '深度测评报告 / 个性化填报报告'
};

function getCurrentUserId() {
  const loginUser = wx.getStorageSync('loginUser') || {};
  const profile = wx.getStorageSync('studentProfile') || {};
  return loginUser.user_id || profile.userId || profile.user_id || '';
}

function fetchEntitlements() {
  const userId = getCurrentUserId();
  return request({
    url: '/api/membership/entitlements',
    data: userId ? { user_id: Number(userId) } : {}
  }).then((res) => {
    wx.setStorageSync('memberEntitlements', res);
    return res;
  });
}

function getCachedEntitlements() {
  return wx.getStorageSync('memberEntitlements') || null;
}

function hasPermission(entitlements, permissionCode) {
  const permissions = entitlements && entitlements.permissions ? entitlements.permissions : {};
  const permission = permissions[permissionCode];
  if (!permission || !permission.enabled) return false;
  const usage = permission.usage || {};
  return Number(permission.limit) < 0 || Number(usage.remaining || 0) > 0;
}

function requirePermission(permissionCode, title, options = {}) {
  const userId = getCurrentUserId();
  if (!userId) {
    showUpgradeModal(permissionCode, title, '请先完善档案后再使用会员功能。');
    return Promise.resolve(false);
  }
  const url = options.consume ? `/api/membership/permissions/${permissionCode}/consume` : `/api/membership/permissions/${permissionCode}/check`;
  return request({ url, method: options.consume ? 'POST' : 'GET', data: { user_id: Number(userId) } })
    .then((res) => {
      if (res.allowed) {
        return fetchEntitlements().then(() => {
          if (res.remaining >= 0 && options.consume) {
            wx.showToast({ title: `剩余${res.remaining}次`, icon: 'none' });
          }
          return true;
        });
      }
      return fetchEntitlements().then((latest) => {
        showUpgradeModal(permissionCode, title, getMembershipStatusMessage(latest) || res.message);
        return false;
      });
    })
    .catch((error) => {
      showUpgradeModal(permissionCode, title, error.message);
      return false;
    });
}


function getMembershipStatusMessage(entitlements) {
  const membership = entitlements && entitlements.membership;
  const latest = entitlements && entitlements.latest_membership;
  if (membership && membership.expires_at) {
    const expiresTime = new Date(String(membership.expires_at).replace(/-/g, '/')).getTime();
    const diffDays = Math.ceil((expiresTime - Date.now()) / 86400000);
    if (diffDays >= 0 && diffDays <= 7) return `您的${membership.plan_name || '会员'}将在${diffDays}天后到期，建议及时续费。`;
  }
  if (!membership && latest && latest.status === 'expired') {
    return `您的${latest.plan_name || '会员'}已过期，续费后可继续使用会员功能。`;
  }
  return '';
}

function showUpgradeModal(permissionCode, title, message) {
  const name = title || PERMISSION_LABELS[permissionCode] || '该功能';
  wx.showModal({
    title: '会员功能',
    content: message || `${name}需要开通对应会员后使用，或当前套餐次数已用完。请前往会员中心微信支付开通。`,
    confirmText: '查看会员',
    cancelText: '稍后再说',
    success: (res) => {
      if (res.confirm) wx.navigateTo({ url: '/pages/membership/membership' });
    }
  });
}

module.exports = {
  fetchEntitlements,
  getCachedEntitlements,
  hasPermission,
  requirePermission,
  getCurrentUserId
};
