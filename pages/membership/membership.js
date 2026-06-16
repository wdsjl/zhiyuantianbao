const { request, formatRequestError, BASE_URL } = require('../../utils/request');
const { getCurrentUserId, syncUserIdentity, fetchEntitlements } = require('../../utils/membership');
const { requestVirtualPayment, getLoginCode } = require('../../utils/virtualPayment');

const { enrichPlan, getPlanDisplayName, SEASON_EXPIRE_LABEL } = require('../../utils/planCatalog');

const PLAN_FEATURES = {
  free: ['完整测评流程', '基础院校专业查询', '近2年分数线', '手动志愿模拟'],
  trial: ['基础性格测评', '院校/专业基础查询', '近2年分数线', '手动志愿模拟', '不含智能推荐与 PDF 导出'],
  premium: ['智能志愿推荐不限次', '志愿风险检测不限次', 'AI 志愿解读与报告', 'PDF 导出不限次', '完整历年分数线', '院校对比与深度分析']
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
    loadError: '',
    seasonExpireLabel: SEASON_EXPIRE_LABEL
  },
  onShow() {
    syncUserIdentity();
    this.loadData();
  },
  mapPlans(list) {
    return (list || [])
      .filter((rawPlan) => rawPlan.plan_code !== 'standard')
      .map((rawPlan) => {
        const plan = enrichPlan(rawPlan);
        const price = Number(plan.price) || 0;
        return {
          ...plan,
          priceText: price === 0 ? '免费' : `¥${price}`,
          displayPriceText: price === 0 ? '免费' : `¥${price}`,
          durationText: price > 0 ? SEASON_EXPIRE_LABEL : '长期',
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
        : Promise.resolve({})
    ];
    Promise.all(tasks)
      .then(([plansRes, entitlementsRes, payStatus, statusRes]) => {
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
            { plan_code: 'trial', plan_name: '普通卡', price: 19.9, duration_days: 1, description: '引流体验卡' },
            { plan_code: 'premium', plan_name: '白金卡', price: 168, duration_days: 1, description: '报考季全功能畅享' }
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
          loadError
        });
      })
      .catch((error) => {
        const message = formatRequestError(error) || '会员信息加载失败';
        this.setData({
          loadError: `${message}。请确认接口地址为 ${BASE_URL}`,
          plans: this.mapPlans([
            { plan_code: 'trial', plan_name: '普通卡', price: 19.9, duration_days: 1, description: '引流体验卡' },
            { plan_code: 'premium', plan_name: '白金卡', price: 168, duration_days: 1, description: '报考季全功能畅享' }
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
          text: `您的${membership.plan_name || '会员'}将在${diffDays}天后到期（${SEASON_EXPIRE_LABEL}），建议及时续费。`,
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
      content: `将支付 ${plan.displayPriceText} 开通「${plan.plan_name}」，${SEASON_EXPIRE_LABEL}。`,
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
            content: `会员已开通，${SEASON_EXPIRE_LABEL}。`,
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
