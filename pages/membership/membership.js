const { request } = require('../../utils/request');
const { fetchEntitlements, getCurrentUserId } = require('../../utils/membership');

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

Page({
  data: {
    loading: false,
    paying: false,
    wechatPayEnabled: false,
    plans: [],
    entitlements: null,
    currentPlanCode: 'free',
    orders: [],
    membershipNotice: null
  },
  onShow() {
    this.loadData();
  },
  loadData() {
    this.setData({ loading: true });
    const userId = getCurrentUserId();
    Promise.all([
      request({ url: '/api/membership/plans' }),
      fetchEntitlements(),
      request({ url: '/api/payments/wechat/status' }).catch(() => ({ enabled: false })),
      this.fetchMyOrders(userId)
    ])
      .then(([plansRes, entitlements, payStatus, orders]) => {
        const currentPlanCode = entitlements.plan ? entitlements.plan.plan_code : 'free';
        const plans = (plansRes.list || []).map((plan) => ({
          ...plan,
          priceText: Number(plan.price) === 0 ? '免费' : `¥${plan.price}`,
          durationText: Number(plan.duration_days) > 0 ? `${plan.duration_days}天` : '长期',
          features: PLAN_FEATURES[plan.plan_code] || [],
          canPay: Number(plan.price) > 0
        }));
        this.setData({
          plans,
          entitlements,
          currentPlanCode,
          wechatPayEnabled: !!payStatus.enabled,
          orders,
          membershipNotice: this.buildMembershipNotice(entitlements, plans)
        });
      })
      .catch(() => {
        wx.showToast({ title: '会员信息加载失败', icon: 'none' });
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
        text: `您的${latest.plan_name || '会员'}已过期，续费后可继续使用会员功能。`,
        priceText: plan ? plan.priceText : ''
      };
    }
    return null;
  },
  fetchMyOrders(userId) {
    if (!userId) return Promise.resolve([]);
    return request({ url: '/api/membership/my-status', data: { user_id: Number(userId) } })
      .then((res) => (res.orders || []).map((item) => ({
        ...item,
        statusText: ORDER_STATUS_TEXT[item.pay_status] || item.pay_status,
        amountText: `¥${item.amount || 0}`
      })))
      .catch(() => []);
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
    this.payForPlan(plan, true);
  },

  payForPlan(eventOrPlan, isRenewal) {
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

    if (!this.data.wechatPayEnabled) {
      wx.showModal({
        title: '支付未就绪',
        content: '微信支付尚未完成服务端配置，请联系管理员配置商户证书和 API 密钥。',
        showCancel: false
      });
      return;
    }

    wx.showModal({
      title: isRenewal ? '确认续费' : '确认支付',
      content: `将支付 ${plan.priceText} 开通「${plan.plan_name}」，有效期 ${plan.durationText}。`,
      confirmText: '立即支付',
      success: (res) => {
        if (!res.confirm) return;
        this.createAndPay(userId, plan, isRenewal);
      }
    });
  },

  createAndPay(userId, plan, isRenewal) {
    this.setData({ paying: true });
    request({
      url: '/api/payments/wechat/create',
      method: 'POST',
      data: {
        user_id: Number(userId),
        plan_code: plan.plan_code,
        request_type: isRenewal ? 'renew' : 'open'
      }
    })
      .then((createRes) => {
        const params = createRes.pay_params || {};
        return new Promise((resolve, reject) => {
          wx.requestPayment({
            timeStamp: params.timeStamp,
            nonceStr: params.nonceStr,
            package: params.package,
            signType: params.signType || 'RSA',
            paySign: params.paySign,
            success: () => resolve(createRes.order_no),
            fail: (error) => reject(error)
          });
        });
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
        if (retry < 5) {
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
