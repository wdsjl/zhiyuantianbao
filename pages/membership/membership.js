const { request, formatRequestError, BASE_URL } = require('../../utils/request');
const { getCurrentUserId, syncUserIdentity, fetchEntitlements } = require('../../utils/membership');

const PLAN_FEATURES = {
  free: ['完整测评流程', '基础院校专业查询', '近2年分数线', '手动志愿模拟'],
  trial: ['完整历年分数线', '深度测评报告', '智能推荐3次', 'AI解读3次', 'PDF导出1次'],
  standard: ['智能推荐不限次', '风险检测不限次', 'AI解读', '草稿保存', 'PDF导出', '专业避坑指南'],
  premium: ['标准年卡全部功能', '同分段往届参考', '院校深度对比', '地域就业规划', '专属答疑通道', '征集志愿提醒']
};

const ORDER_STATUS_TEXT = {
  pending: '待支付',
  paid: '已支付',
  refunded: '已退款',
  cancelled: '已取消'
};

const REQUEST_STATUS_TEXT = {
  pending: '待处理',
  processed: '已开通',
  cancelled: '已取消'
};

Page({
  data: {
    loading: false,
    submitting: false,
    plans: [],
    entitlements: null,
    currentPlanCode: 'free',
    orders: [],
    openRequests: [],
    supportContact: {},
    membershipNotice: null,
    loadError: ''
  },
  onShow() {
    syncUserIdentity();
    this.loadData();
  },
  mapPlans(list) {
    return (list || []).map((plan) => ({
      ...plan,
      priceText: Number(plan.price) === 0 ? '免费' : `¥${plan.price}`,
      durationText: Number(plan.duration_days) > 0 ? `${plan.duration_days}天` : '长期',
      features: PLAN_FEATURES[plan.plan_code] || [],
      canApply: Number(plan.price) > 0
    }));
  },
  loadData() {
    this.setData({ loading: true, loadError: '' });
    const userId = getCurrentUserId();
    const tasks = [
      request({ url: '/api/membership/plans' }).catch((error) => ({ error })),
      fetchEntitlements().catch((error) => ({ error })),
      request({ url: '/api/membership/support-contact' }).catch(() => ({})),
      userId
        ? request({ url: '/api/membership/my-status', data: { user_id: Number(userId) } }).catch(() => ({}))
        : Promise.resolve({})
    ];
    Promise.all(tasks)
      .then(([plansRes, entitlementsRes, supportContact, statusRes]) => {
        const errors = [];
        if (plansRes && plansRes.error) errors.push(`套餐列表：${formatRequestError(plansRes.error)}`);
        if (entitlementsRes && entitlementsRes.error) errors.push(`会员状态：${formatRequestError(entitlementsRes.error)}`);

        const entitlements = entitlementsRes && entitlementsRes.error
          ? { plan: { plan_name: '免费版', plan_code: 'free' }, membership: null, latest_membership: null, permissions: {} }
          : entitlementsRes;
        const plans = plansRes && !plansRes.error
          ? this.mapPlans(plansRes.list)
          : this.mapPlans([
            { plan_code: 'free', plan_name: '免费版', price: 0, duration_days: 0, description: '基础永久免费，引流体验' },
            { plan_code: 'trial', plan_name: '体验月卡', price: 19.9, duration_days: 30, description: '30 天体验核心能力' },
            { plan_code: 'standard', plan_name: '标准年卡', price: 99, duration_days: 365, description: '主推款，智能推荐、风险检测、AI 解读、PDF 导出' },
            { plan_code: 'premium', plan_name: '尊享年卡', price: 168, duration_days: 365, description: '深度对比、提醒、答疑通道' }
          ]);

        const currentPlanCode = entitlements.plan ? entitlements.plan.plan_code : 'free';
        const loadError = errors.length
          ? `${errors.join('；')}。请确认接口地址为 ${BASE_URL}`
          : '';

        this.setData({
          plans,
          entitlements,
          currentPlanCode,
          supportContact: supportContact || {},
          orders: (statusRes.orders || []).map((item) => ({
            ...item,
            statusText: ORDER_STATUS_TEXT[item.pay_status] || item.pay_status,
            amountText: `¥${item.amount || 0}`
          })),
          openRequests: (statusRes.requests || []).map((item) => ({
            ...item,
            statusText: REQUEST_STATUS_TEXT[item.request_status] || item.request_status
          })),
          membershipNotice: this.buildMembershipNotice(entitlements, plans),
          loadError
        });
      })
      .catch((error) => {
        const message = formatRequestError(error) || '会员信息加载失败';
        this.setData({
          loadError: `${message}。请确认接口地址为 ${BASE_URL}`,
          plans: this.mapPlans([
            { plan_code: 'trial', plan_name: '体验月卡', price: 19.9, duration_days: 30, description: '30 天体验核心能力' },
            { plan_code: 'standard', plan_name: '标准年卡', price: 99, duration_days: 365, description: '主推款' },
            { plan_code: 'premium', plan_name: '尊享年卡', price: 168, duration_days: 365, description: '深度对比、提醒、答疑通道' }
          ]),
          entitlements: { plan: { plan_name: '免费版', plan_code: 'free' }, membership: null, permissions: {} }
        });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },

  buildMembershipNotice(entitlements, plans) {
    const membership = entitlements.membership;
    const latest = entitlements.latest_membership;
    if (membership && membership.expires_at) {
      const expiresTime = new Date(String(membership.expires_at).replace(/-/g, '/')).getTime();
      const diffDays = Math.ceil((expiresTime - Date.now()) / 86400000);
      if (diffDays >= 0 && diffDays <= 7) {
        const plan = plans.find((item) => item.plan_code === membership.plan_code);
        return {
          type: 'warning',
          planCode: membership.plan_code,
          planName: membership.plan_name || '会员',
          text: `您的${membership.plan_name || '会员'}将在${diffDays}天后到期，可提交续费申请。`,
          priceText: plan ? plan.priceText : ''
        };
      }
      return null;
    }
    if (!membership && latest && latest.status === 'expired') {
      const plan = plans.find((item) => item.plan_code === latest.plan_code);
      return {
        type: 'expired',
        planCode: latest.plan_code,
        planName: latest.plan_name || '会员',
        text: `您的${latest.plan_name || '会员'}已过期，可提交续费申请。`,
        priceText: plan ? plan.priceText : ''
      };
    }
    return null;
  },

  ensureUserReady() {
    const userId = getCurrentUserId();
    if (!userId) {
      wx.showModal({
        title: '请先完善档案',
        content: '开通会员前，请先完成登录和学生档案。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
        }
      });
      return null;
    }
    return userId;
  },

  renewCurrentPlan() {
    const notice = this.data.membershipNotice;
    if (!notice || !notice.planCode) return;
    const plan = this.data.plans.find((item) => item.plan_code === notice.planCode);
    if (!plan) {
      wx.showToast({ title: '套餐信息加载失败', icon: 'none' });
      return;
    }
    this.submitOpenRequest(plan, true);
  },

  submitOpenRequest(eventOrPlan, isRenewal) {
    const plan = eventOrPlan && eventOrPlan.currentTarget
      ? this.data.plans[eventOrPlan.currentTarget.dataset.index]
      : eventOrPlan;
    if (!plan || this.data.submitting) return;

    const userId = this.ensureUserReady();
    if (!userId) return;

    if (!plan.canApply) {
      wx.showToast({ title: '当前套餐无需开通', icon: 'none' });
      return;
    }

    const profile = wx.getStorageSync('studentProfile') || {};
    wx.showModal({
      title: isRenewal ? '提交续费申请' : '提交开通申请',
      content: `将提交「${plan.plan_name}」（${plan.priceText}）开通申请。客服确认后会为您开通会员，请按页面说明联系客服。`,
      confirmText: '提交申请',
      success: (res) => {
        if (!res.confirm) return;
        this.doSubmitOpenRequest(userId, plan, isRenewal, profile);
      }
    });
  },

  doSubmitOpenRequest(userId, plan, isRenewal, profile) {
    this.setData({ submitting: true });
    request({
      url: '/api/membership/open-requests',
      method: 'POST',
      data: {
        user_id: Number(userId),
        plan_code: plan.plan_code,
        contact_name: profile.name || '',
        contact_phone: profile.phone || '',
        message: `${isRenewal ? '续费' : '开通'}${plan.plan_name}`,
        request_type: isRenewal ? 'renew' : 'open'
      }
    })
      .then((res) => {
        const support = this.data.supportContact || {};
        const note = support.support_note || '申请已提交，请联系客服并备注手机号与套餐名称。';
        wx.showModal({
          title: res.duplicate ? '已提交过申请' : '申请已提交',
          content: `${res.message || '客服确认后会为您开通会员。'}\n\n${note}${support.support_wechat ? `\n客服微信：${support.support_wechat}` : ''}${support.support_phone ? `\n客服电话：${support.support_phone}` : ''}`,
          confirmText: support.support_wechat ? '复制客服微信' : '知道了',
          cancelText: '关闭',
          success: (modalRes) => {
            if (modalRes.confirm && support.support_wechat) {
              wx.setClipboardData({ data: support.support_wechat });
            }
          }
        });
        this.loadData();
      })
      .catch((error) => {
        wx.showToast({ title: error.message || '提交失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ submitting: false });
      });
  },

  copySupportWechat() {
    const wechat = (this.data.supportContact || {}).support_wechat;
    if (!wechat) {
      wx.showToast({ title: '暂未配置客服微信', icon: 'none' });
      return;
    }
    wx.setClipboardData({ data: wechat });
  },

  callSupportPhone() {
    const phone = (this.data.supportContact || {}).support_phone;
    if (!phone) {
      wx.showToast({ title: '暂未配置客服电话', icon: 'none' });
      return;
    }
    wx.makePhoneCall({ phoneNumber: phone });
  }
});
