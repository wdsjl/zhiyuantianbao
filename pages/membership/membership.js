const { request, formatRequestError, BASE_URL } = require('../../utils/request');
const { getCurrentUserId, syncUserIdentity, fetchEntitlements } = require('../../utils/membership');
const { requestVirtualPayment, getLoginCode } = require('../../utils/virtualPayment');

const { enrichPlan, getPlanDisplayName, PLAN_BEAN_GRANT } = require('../../utils/planCatalog');

const PLAN_FEATURES = {
  free: ['完整测评流程', '基础院校专业查询', '近2年分数线', '手动志愿模拟'],
  trial: ['到账 2000 星鼎豆', '完整历年分数线', '深度测评报告', '智能推荐', 'AI 解读', 'PDF 导出'],
  standard: ['到账 12000 星鼎豆', '智能推荐不限次', '风险检测不限次', 'AI 解读', '草稿保存', 'PDF 导出'],
  premium: ['到账 24000 星鼎豆', '金卡全部功能', '同分段往届参考', '院校深度对比', '地域就业规划', '专属答疑通道']
};

const ORDER_STATUS_TEXT = {
  pending: '待支付',
  paid: '已支付',
  refunded: '已退款',
  cancelled: '已取消'
};

Page({
  data: {
    loading: false,
    paying: false,
    virtualPayEnabled: false,
    plans: [],
    entitlements: null,
    currentPlanCode: 'free',
    currentPlanName: '免费版',
    orders: [],
    membershipNotice: null,
    beanBalance: 0,
    loadError: '',
    douyinRedeemCode: '',
    douyinRedeeming: false
  },
  onShow() {
    syncUserIdentity();
    this.loadData();
    this.scrollToDouyinIfNeeded();
  },
  scrollToDouyinIfNeeded() {
    if (wx.getStorageSync('membershipScrollTarget') !== 'douyin') return;
    wx.removeStorageSync('membershipScrollTarget');
    setTimeout(() => {
      wx.pageScrollTo({ selector: '.douyin-redeem-card', duration: 300 });
    }, 400);
  },
  mapPlans(list) {
    return (list || []).map((rawPlan) => {
      const plan = enrichPlan(rawPlan);
      const price = Number(plan.price) || 0;
      const beanGrant = plan.beanGrant || PLAN_BEAN_GRANT[plan.plan_code] || 0;
      return {
        ...plan,
        priceText: price === 0 ? '免费' : `¥${price}`,
        beanGrant,
        beanPriceText: beanGrant > 0 ? `${beanGrant}星鼎豆` : '免费',
        displayPriceText: beanGrant > 0 ? `¥${price} · ${beanGrant}星鼎豆` : '免费',
        durationText: Number(plan.duration_days) > 0 ? `${plan.duration_days}天` : '长期',
        features: PLAN_FEATURES[plan.plan_code] || [],
        canPay: price > 0
      };
    });
  },
  loadData() {
    this.setData({ loading: true, loadError: '' });
    const userId = getCurrentUserId();
    const tasks = [
      request({ url: '/api/membership/plans' }).catch((error) => ({ error })),
      fetchEntitlements().catch((error) => ({ error })),
      request({ url: '/api/payments/wechat/status' }).catch(() => ({ enabled: false })),
      userId
        ? request({ url: '/api/membership/my-status', data: { user_id: Number(userId) } }).catch(() => ({}))
        : Promise.resolve({}),
      userId
        ? request({ url: '/api/membership/beans', data: { user_id: Number(userId) } }).catch(() => ({ balance: 0 }))
        : Promise.resolve({ balance: 0 })
    ];
    Promise.all(tasks)
      .then(([plansRes, entitlementsRes, payStatus, statusRes, beanRes]) => {
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
            { plan_code: 'trial', plan_name: '普通卡', price: 19.9, duration_days: 30, description: '一次充值 ¥19.9，到账 2000 星鼎豆' },
            { plan_code: 'standard', plan_name: '金卡', price: 99, duration_days: 365, description: '起充 ¥99，到账 12000 星鼎豆' },
            { plan_code: 'premium', plan_name: '白金卡', price: 168, duration_days: 365, description: '起充 ¥168，到账 24000 星鼎豆' }
          ]);

        const currentPlanCode = entitlements.plan ? entitlements.plan.plan_code : 'free';
        const currentPlanName = getPlanDisplayName(currentPlanCode, entitlements.plan && entitlements.plan.plan_name);
        const loadError = errors.length
          ? `${errors.join('；')}。请确认接口地址为 ${BASE_URL}`
          : '';

        this.setData({
          plans,
          entitlements: {
            ...entitlements,
            plan: {
              ...(entitlements.plan || { plan_code: 'free', plan_name: '免费版' }),
              plan_name: currentPlanName
            }
          },
          currentPlanCode,
          currentPlanName,
          virtualPayEnabled: !!payStatus.enabled,
          orders: (statusRes.orders || []).map((item) => ({
            ...item,
            statusText: ORDER_STATUS_TEXT[item.pay_status] || item.pay_status,
            amountText: `¥${item.amount || 0}`
          })),
          membershipNotice: this.buildMembershipNotice(entitlements, plans),
          beanBalance: Number(beanRes.balance) || 0,
          loadError
        });
      })
      .catch((error) => {
        const message = formatRequestError(error) || '会员信息加载失败';
        this.setData({
          loadError: `${message}。请确认接口地址为 ${BASE_URL}`,
          plans: this.mapPlans([
            { plan_code: 'trial', plan_name: '普通卡', price: 19.9, duration_days: 30, description: '一次充值 ¥19.9，到账 2000 星鼎豆' },
            { plan_code: 'standard', plan_name: '金卡', price: 99, duration_days: 365, description: '起充 ¥99，到账 12000 星鼎豆' },
            { plan_code: 'premium', plan_name: '白金卡', price: 168, duration_days: 365, description: '起充 ¥168，到账 24000 星鼎豆' }
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
          text: `您的${membership.plan_name || '会员'}将在${diffDays}天后到期，建议及时续费。`,
          priceText: plan ? plan.displayPriceText : ''
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
        text: `您的${latest.plan_name || '会员'}已过期，续费后可继续使用会员功能。`,
        priceText: plan ? plan.displayPriceText : ''
      };
    }
    return null;
  },

  ensureUserReady() {
    const userId = getCurrentUserId();
    if (!userId) {
      wx.showModal({
        title: '请先完善档案',
        content: '支付开通会员前，请先完成登录和学生档案。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
        }
      });
      return null;
    }
    return userId;
  },

  onDouyinCodeInput(event) {
    this.setData({ douyinRedeemCode: (event.detail.value || '').trim().toUpperCase() });
  },

  submitDouyinRedeem() {
    const userId = this.ensureUserReady();
    if (!userId) return;
    const couponCode = (this.data.douyinRedeemCode || '').trim().toUpperCase();
    if (!couponCode) {
      wx.showToast({ title: '请输入兑换码', icon: 'none' });
      return;
    }
    this.setData({ douyinRedeeming: true });
    request({
      url: '/api/douyin/redeem',
      method: 'POST',
      data: {
        user_id: Number(userId),
        coupon_code: couponCode
      }
    })
      .then((res) => {
        wx.showModal({
          title: res.already_redeemed ? '已兑换' : '兑换成功',
          content: res.message || '会员已开通',
          showCancel: false,
          success: () => {
            this.setData({ douyinRedeemCode: '' });
            fetchEntitlements();
            this.loadData();
          }
        });
      })
      .catch((error) => {
        wx.showModal({
          title: '兑换失败',
          content: formatRequestError(error) || '请检查兑换码后重试',
          showCancel: false
        });
      })
      .finally(() => {
        this.setData({ douyinRedeeming: false });
      });
  },

  renewCurrentPlan() {
    const notice = this.data.membershipNotice;
    if (!notice || !notice.planCode) return;
    const plan = this.data.plans.find((item) => item.plan_code === notice.planCode);
    if (!plan) {
      wx.showToast({ title: '套餐信息加载失败', icon: 'none' });
      return;
    }
    this.startPay(plan, true);
  },

  startPay(eventOrPlan, isRenewal) {
    const plan = eventOrPlan && eventOrPlan.currentTarget
      ? this.data.plans[eventOrPlan.currentTarget.dataset.index]
      : eventOrPlan;
    if (!plan || this.data.paying) return;

    const userId = this.ensureUserReady();
    if (!userId) return;

    if (!plan.canPay) {
      wx.showToast({ title: '当前套餐无需支付', icon: 'none' });
      return;
    }

    if (!this.data.virtualPayEnabled) {
      const status = this.data.payStatusDetail || {};
      const missing = (status.missing || []).join('、') || 'WECHAT_SECRET / WECHAT_VIRTUAL_PAY_APP_KEY';
      wx.showModal({
        title: '虚拟支付未就绪',
        content: `服务端尚未完成虚拟支付配置，无需商户证书。\n\n请管理员在 ecosystem.secrets.js 填写：\n${missing}\n\n配置后执行：pm2 restart zhiyuan-backend --update-env\n\n${status.hint || ''}`,
        showCancel: false
      });
      return;
    }

    wx.showModal({
      title: isRenewal ? '确认续费' : '确认支付',
      content: `将支付 ${plan.displayPriceText} 开通「${plan.plan_name}」，有效期 ${plan.durationText}。`,
      confirmText: '立即支付',
      success: (res) => {
        if (!res.confirm) return;
        this.createAndPay(userId, plan, isRenewal);
      }
    });
  },

  createAndPay(userId, plan, isRenewal) {
    this.setData({ paying: true });
    getLoginCode()
      .then((loginCode) => request({
        url: '/api/payments/wechat/create',
        method: 'POST',
        data: {
          user_id: Number(userId),
          plan_code: plan.plan_code,
          request_type: isRenewal ? 'renew' : 'open',
          login_code: loginCode
        }
      }))
      .then((createRes) => {
        const virtualPay = createRes.virtual_pay || {};
        return requestVirtualPayment({
          mode: createRes.mode || 'short_series_goods',
          signData: virtualPay.signData,
          paySig: virtualPay.paySig,
          signature: virtualPay.signature
        }).then(() => createRes.order_no);
      })
      .then((orderNo) => this.confirmPayment(orderNo))
      .catch((error) => {
        if (error && error.errMsg && error.errMsg.includes('cancel')) {
          wx.showToast({ title: '已取消支付', icon: 'none' });
          return;
        }
        wx.showModal({
          title: '支付失败',
          content: (error && error.message) || (error && error.errMsg) || '请稍后重试',
          showCancel: false
        });
      })
      .finally(() => {
        this.setData({ paying: false });
      });
  },

  confirmPayment(orderNo, retry = 0) {
    const userId = getCurrentUserId();
    return request({
      url: `/api/payments/wechat/orders/${orderNo}`,
      data: { user_id: Number(userId) }
    })
      .then((res) => {
        const order = res.order || {};
        if (order.pay_status === 'paid') {
          wx.showModal({
            title: '支付成功',
            content: '会员已开通，相关功能现在可以使用了。',
            showCancel: false,
            success: () => {
              fetchEntitlements();
              this.loadData();
            }
          });
          return;
        }
        if (retry < 8) {
          return new Promise((resolve) => {
            setTimeout(() => resolve(this.confirmPayment(orderNo, retry + 1)), 1200);
          });
        }
        wx.showModal({
          title: '支付处理中',
          content: '支付结果确认中，请稍后在会员中心查看订单状态。',
          showCancel: false,
          success: () => this.loadData()
        });
      });
  }
});
