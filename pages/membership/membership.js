const { request } = require('../../utils/request');
const { fetchEntitlements, getCurrentUserId } = require('../../utils/membership');

const PLAN_FEATURES = {
  free: ['完整测评流程', '基础院校专业查询', '近2年分数线', '手动志愿模拟'],
  trial: ['完整历年分数线', '深度测评报告', '智能推荐3次', 'AI解读3次', 'PDF导出1次'],
  standard: ['智能推荐不限次', '风险检测不限次', 'AI解读', '草稿保存', 'PDF导出', '专业避坑指南'],
  premium: ['标准年卡全部功能', '同分段往届参考', '院校深度对比', '地域就业规划', '专属答疑通道', '征集志愿提醒']
};

const REQUEST_STATUS_TEXT = {
  pending: '待处理',
  processed: '已开通',
  cancelled: '已取消'
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
    applying: false,
    plans: [],
    entitlements: null,
    currentPlanCode: 'free',
    openRequests: [],
    orders: [],
    supportContact: null,
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
      this.fetchMyStatus(userId),
      request({ url: '/api/membership/support-contact' }).catch(() => null)
    ])
      .then(([plansRes, entitlements, status, supportContact]) => {
        const currentPlanCode = entitlements.plan ? entitlements.plan.plan_code : 'free';
        const plans = (plansRes.list || []).map((plan) => ({
          ...plan,
          priceText: Number(plan.price) === 0 ? '免费' : `¥${plan.price}`,
          durationText: Number(plan.duration_days) > 0 ? `${plan.duration_days}天` : '长期',
          features: PLAN_FEATURES[plan.plan_code] || []
        }));
        this.setData({ plans, entitlements, currentPlanCode, openRequests: status.requests, orders: status.orders, supportContact, membershipNotice: this.buildMembershipNotice(entitlements, plans) });
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
        return { type: 'warning', planCode: membership.plan_code, planName: membership.plan_name || '会员', text: `您的${membership.plan_name || '会员'}将在${diffDays}天后到期，建议及时续费。`, priceText: plan ? plan.priceText : '' };
      }
      return null;
    }
    if (!membership && latest && latest.status === 'expired') {
      const plan = plans.find((item) => item.plan_code === latest.plan_code);
      return { type: 'expired', planCode: latest.plan_code, planName: latest.plan_name || '会员', text: `您的${latest.plan_name || '会员'}已过期，续费后可继续使用会员功能。`, priceText: plan ? plan.priceText : '' };
    }
    return null;
  },
  fetchMyStatus(userId) {
    if (!userId) return Promise.resolve({ requests: [], orders: [] });
    return request({ url: '/api/membership/my-status', data: { user_id: Number(userId) } })
      .then((res) => ({
        requests: (res.requests || []).map((item) => ({
          ...item,
          statusText: REQUEST_STATUS_TEXT[item.request_status] || item.request_status,
          priceText: `¥${item.price || 0}`
        })),
        orders: (res.orders || []).map((item) => ({
          ...item,
          statusText: ORDER_STATUS_TEXT[item.pay_status] || item.pay_status,
          amountText: `¥${item.amount || 0}`
        }))
      }))
      .catch(() => ({ requests: [], orders: [] }));
  },

  buildApplySuccessMessage(submitRes) {
    const contact = this.data.supportContact || {};
    const lines = [submitRes.message || '客服确认收款后会为您开通会员。'];
    if (contact.support_wechat) lines.push(`客服微信：${contact.support_wechat}`);
    if (contact.support_phone) lines.push(`客服电话：${contact.support_phone}`);
    if (contact.support_note) lines.push(contact.support_note);
    return lines.join('\n');
  },
  renewCurrentPlan() {
    const notice = this.data.membershipNotice;
    if (!notice || !notice.planCode) return;
    const plan = this.data.plans.find((item) => item.plan_code === notice.planCode);
    if (!plan) {
      wx.showToast({ title: '套餐信息加载失败', icon: 'none' });
      return;
    }
    this.submitPlanRequest(plan, true);
  },
  contactOpen(event) {
    const plan = this.data.plans[event.currentTarget.dataset.index];
    if (!plan) return;
    this.submitPlanRequest(plan, false);
  },
  submitPlanRequest(plan, isRenewal) {
    if (this.data.applying) return;
    const userId = getCurrentUserId();
    const loginUser = wx.getStorageSync('loginUser') || {};
    const profile = wx.getStorageSync('studentProfile') || {};
    if (!userId) {
      wx.showModal({
        title: '请先完善档案',
        content: '提交会员开通申请前，请先完成登录和学生档案。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
        }
      });
      return;
    }
    wx.showModal({
      title: isRenewal ? '提交续费申请' : '提交开通申请',
      content: `是否提交「${plan.plan_name}」${isRenewal ? '续费' : '开通'}申请？客服确认收款后会为您处理。`,
      confirmText: '提交申请',
      success: (res) => {
        if (!res.confirm) return;
        this.setData({ applying: true });
        request({
          url: '/api/membership/open-requests',
          method: 'POST',
          data: {
            user_id: Number(userId),
            plan_code: plan.plan_code,
            contact_name: profile.name || loginUser.name || '',
            contact_phone: profile.phone || loginUser.phone || '',
            message: `${isRenewal ? '申请续费' : '申请开通'}${plan.plan_name}，套餐金额${plan.priceText}`,
            request_type: isRenewal ? 'renew' : 'open'
          }
        })
          .then((submitRes) => {
            wx.showModal({
              title: submitRes.duplicate ? '申请已存在' : '申请已提交',
              content: this.buildApplySuccessMessage(submitRes),
              confirmText: '复制套餐',
              cancelText: '知道了',
              success: (copyRes) => {
                if (copyRes.confirm) wx.setClipboardData({ data: `${plan.plan_name} ${plan.priceText}` });
              }
            });
            this.loadData();
          })
          .catch((error) => {
            wx.showToast({ title: error.message || '提交失败', icon: 'none' });
          })
          .finally(() => {
            this.setData({ applying: false });
          });
      }
    });
  }
});

