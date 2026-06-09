const { request } = require('../../utils/request');
const { ensureWechatLogin } = require('../../utils/auth');
const { getCurrentUserId } = require('../../utils/membership');

const STATUS_TEXT = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  paid: '已打款'
};

Page({
  data: {
    wallet: {},
    withdrawals: [],
    amount: '',
    payMethods: ['微信', '支付宝', '银行卡'],
    payMethodValues: ['wechat', 'alipay', 'bank'],
    payMethodIndex: 0,
    payAccount: '',
    payName: '',
    submitting: false
  },
  onShow() {
    this.loadData();
  },
  loadData() {
    ensureWechatLogin().then(() => {
      const userId = Number(getCurrentUserId());
      return Promise.all([
        request({ url: '/api/referral/dashboard', data: { user_id: userId } }),
        request({ url: '/api/referral/withdrawals', data: { user_id: userId } })
      ]);
    }).then(([dashboard, withdrawRes]) => {
      const withdrawals = (withdrawRes.list || []).map((item) => ({
        ...item,
        statusText: STATUS_TEXT[item.status] || item.status
      }));
      this.setData({
        wallet: dashboard.wallet || {},
        withdrawals
      });
    }).catch((error) => wx.showToast({ title: error.message || '加载失败', icon: 'none' }));
  },
  onAmountInput(e) {
    this.setData({ amount: e.detail.value });
  },
  onAccountInput(e) {
    this.setData({ payAccount: e.detail.value });
  },
  onNameInput(e) {
    this.setData({ payName: e.detail.value });
  },
  onPayMethodChange(e) {
    this.setData({ payMethodIndex: Number(e.detail.value) });
  },
  submitWithdraw() {
    const userId = Number(getCurrentUserId());
    const amount = Number(this.data.amount);
    if (!amount || amount <= 0) {
      wx.showToast({ title: '请输入提现金额', icon: 'none' });
      return;
    }
    if (!this.data.payAccount) {
      wx.showToast({ title: '请填写收款账号', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    request({
      url: '/api/referral/withdraw',
      method: 'POST',
      data: {
        user_id: userId,
        amount,
        pay_method: this.data.payMethodValues[this.data.payMethodIndex],
        pay_account: this.data.payAccount,
        pay_name: this.data.payName
      }
    }).then(() => {
      wx.showToast({ title: '已提交申请' });
      this.setData({ amount: '', payAccount: '', payName: '' });
      this.loadData();
    }).catch((error) => {
      wx.showModal({ title: '提现失败', content: error.message || '请稍后重试', showCancel: false });
    }).finally(() => this.setData({ submitting: false }));
  }
});
