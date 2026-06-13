const { request } = require('./request');
const { isTempOpenid } = require('./auth');

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

function syncUserIdentity() {
  const loginUser = wx.getStorageSync('loginUser') || {};
  const profile = wx.getStorageSync('studentProfile') || {};
  const loginId = loginUser.user_id || loginUser.userId || '';
  const profileId = profile.userId || profile.user_id || '';
  if (loginId && profileId && String(loginId) !== String(profileId)) {
    const updated = {
      ...profile,
      userId: loginId,
      openid: loginUser.openid || profile.openid
    };
    wx.setStorageSync('studentProfile', updated);
    return String(loginId);
  }
  const resolved = loginId || profileId || '';
  if (resolved && profile && String(profile.userId || '') !== String(resolved)) {
    wx.setStorageSync('studentProfile', { ...profile, userId: resolved });
  }
  return String(resolved);
}

function getCurrentUserId() {
  return syncUserIdentity();
}

function refreshUserIdentityFromServer() {
  const profile = wx.getStorageSync('studentProfile') || {};
  const loginUser = wx.getStorageSync('loginUser') || {};
  const openid = loginUser.openid || profile.openid || '';
  const phone = profile.phone || loginUser.phone || '';
  if (!phone && (!openid || isTempOpenid(openid))) {
    return Promise.resolve(getCurrentUserId());
  }
  const query = phone ? { phone } : { openid };
  return request({ url: '/api/profile', data: query })
    .then((res) => {
      const serverProfile = res.profile || {};
      if (!serverProfile.user_id) return getCurrentUserId();
      const updatedProfile = {
        ...profile,
        userId: serverProfile.user_id,
        studentId: serverProfile.student_id || profile.studentId,
        openid: serverProfile.openid || openid,
        phone: serverProfile.phone || phone,
        name: serverProfile.name || profile.name,
        province: serverProfile.province || profile.province,
        score: serverProfile.score || profile.score,
        rank: serverProfile.rank || profile.rank,
        subjectCombination: serverProfile.subject_combination || profile.subjectCombination,
        targetBatch: serverProfile.target_batch || profile.targetBatch
      };
      wx.setStorageSync('studentProfile', updatedProfile);
      wx.setStorageSync('loginUser', {
        ...loginUser,
        user_id: serverProfile.user_id,
        openid: serverProfile.openid || openid,
        has_profile: true
      });
      wx.removeStorageSync('memberEntitlements');
      return String(serverProfile.user_id);
    })
    .catch(() => getCurrentUserId());
}

function fetchEntitlements() {
  return refreshUserIdentityFromServer().then((userId) => request({
    url: '/api/membership/entitlements',
    data: userId ? { user_id: Number(userId) } : {}
  }).then((res) => {
    wx.setStorageSync('memberEntitlements', res);
    return res;
  }));
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
  wx.removeStorageSync('memberEntitlements');
  return refreshUserIdentityFromServer()
    .then(() => fetchEntitlements().catch(() => null))
    .then(() => {
      const userId = getCurrentUserId();
      if (!userId) {
        showUpgradeModal(permissionCode, title, '请先完善档案后再使用会员功能。');
        return false;
      }
      const action = options.consume ? 'consume' : 'check';
      const url = `/api/membership/permissions/${permissionCode}/${action}?user_id=${Number(userId)}`;
      return request({ url, method: options.consume ? 'POST' : 'GET' })
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
            const planName = latest && latest.plan ? latest.plan.plan_name : '免费版';
            const hint = getMembershipStatusMessage(latest)
              || res.message
              || `当前套餐为「${planName}」，未开通该功能或次数已用完。`;
            showUpgradeModal(permissionCode, title, hint);
            return false;
          });
        })
        .catch((error) => {
          showUpgradeModal(permissionCode, title, error.message || '权限校验失败，请稍后重试');
          return false;
        });
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

function goMembershipPage() {
  wx.switchTab({ url: '/pages/membership/membership' });
}

function goDouyinRedeemPage() {
  wx.setStorageSync('membershipScrollTarget', 'douyin');
  goMembershipPage();
}

function showUpgradeModal(permissionCode, title, message) {
  const name = title || PERMISSION_LABELS[permissionCode] || '该功能';
  wx.showModal({
    title: '会员功能',
    content: message || `${name}需要开通对应会员后使用，或当前套餐次数已用完。请前往会员中心使用星鼎豆支付开通。`,
    confirmText: '查看会员',
    cancelText: '稍后再说',
    success: (res) => {
      if (res.confirm) goMembershipPage();
    }
  });
}

module.exports = {
  fetchEntitlements,
  getCachedEntitlements,
  hasPermission,
  requirePermission,
  getCurrentUserId,
  syncUserIdentity,
  refreshUserIdentityFromServer,
  goMembershipPage,
  goDouyinRedeemPage
};
