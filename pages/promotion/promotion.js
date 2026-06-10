const { request } = require('../../utils/request');
const { ensureWechatLogin } = require('../../utils/auth');
const { getCurrentUserId } = require('../../utils/membership');
const { base64ToTempFilePath } = require('../../utils/posterHelper');

Page({
  data: {
    loading: true,
    days: 30,
    agent: {},
    invitees: [],
    commissions: [],
    pendingCommission: 0,
    wallet: {},
    rangeStats: {},
    materials: [],
    templates: [],
    templateKey: 'blue',
    qrImage: '',
    qrPath: '',
    qrError: '',
    scanReward: {},
    composedPoster: '',
    level: {},
    faqs: [],
    expandedFaqId: null
  },
  onShow() {
    this.loadDashboard();
  },
  loadDashboard() {
    this.setData({ loading: true });
    ensureWechatLogin()
      .then(() => {
        const userId = getCurrentUserId();
        if (!userId) throw new Error('请先登录');
        return request({ url: '/api/referral/agent/register', method: 'POST', data: { user_id: Number(userId) } })
          .then(() => Promise.all([
            request({ url: '/api/referral/dashboard', data: { user_id: Number(userId), days: this.data.days } }),
            request({ url: '/api/referral/materials' }),
            request({ url: '/api/referral/faqs' }),
            request({ url: '/api/referral/scan-reward' })
          ]));
      })
      .then(([dashboard, materialsRes, faqRes, scanReward]) => {
        this.setData({
          loading: false,
          agent: dashboard.agent || {},
          invitees: dashboard.invitees || [],
          commissions: dashboard.commissions || [],
          pendingCommission: dashboard.pending_commission || 0,
          wallet: dashboard.wallet || {},
          rangeStats: dashboard.range_stats || {},
          materials: materialsRes.list || [],
          level: dashboard.level || {},
          faqs: faqRes.list || [],
          scanReward: scanReward || {},
          composedPoster: ''
        });
        this.loadPoster();
      })
      .catch((error) => {
        this.setData({ loading: false });
        wx.showToast({ title: error.message || '加载失败', icon: 'none' });
      });
  },
  loadPoster() {
    const userId = getCurrentUserId();
    if (!userId) return Promise.resolve();
    return request({ url: '/api/referral/poster', data: { user_id: Number(userId), template_key: this.data.templateKey } })
      .then((poster) => this.applyPosterData(poster))
      .catch((error) => {
        this.setData({ qrError: error.message || '二维码加载失败', qrImage: '', qrPath: '', composedPoster: '' });
      });
  },
  applyPosterData(poster) {
    const qrBase64 = poster && poster.image_base64 ? poster.image_base64 : '';
    const posterBase64 = poster && poster.poster_base64 ? poster.poster_base64 : '';
    const scanReward = poster.scan_reward || this.data.scanReward || {};
    const qrError = poster.qr_error || '';
    const baseState = {
      templates: poster.templates || [],
      templateKey: (poster.template && poster.template.template_key) || this.data.templateKey,
      scanReward,
      qrError: qrError || (!qrBase64 ? '未获取到小程序码，请检查服务端 WECHAT_SECRET 配置' : '')
    };
    if (!qrBase64 && !posterBase64) {
      this.setData({
        ...baseState,
        qrImage: '',
        qrPath: '',
        composedPoster: ''
      });
      return Promise.resolve();
    }
    const tasks = [];
    if (qrBase64) {
      tasks.push(
        base64ToTempFilePath(qrBase64, `poster_qr_${poster.invite_code || 'agent'}.png`)
          .then((qrPath) => ({ qrPath }))
      );
    }
    if (posterBase64) {
      tasks.push(
        base64ToTempFilePath(posterBase64, `poster_full_${poster.invite_code || 'agent'}.png`)
          .then((composedPoster) => ({ composedPoster }))
      );
    }
    return Promise.all(tasks)
      .then((results) => {
        const merged = results.reduce((acc, item) => Object.assign(acc, item), {});
        this.setData({
          ...baseState,
          qrPath: merged.qrPath || '',
          qrImage: merged.qrPath || '',
          composedPoster: merged.composedPoster || '',
          qrError: merged.qrPath || merged.composedPoster ? '' : baseState.qrError
        });
      })
      .catch((error) => {
        this.setData({
          ...baseState,
          qrImage: '',
          qrPath: '',
          composedPoster: '',
          qrError: error.message || qrError || '海报解析失败'
        });
      });
  },
  onDaysChange(e) {
    const days = Number(e.currentTarget.dataset.days || 30);
    this.setData({ days }, () => this.loadDashboard());
  },
  onTemplateChange(e) {
    const templateKey = e.currentTarget.dataset.key;
    this.setData({ templateKey, composedPoster: '' }, () => this.loadPoster());
  },
  composePoster() {
    wx.showLoading({ title: '刷新海报中' });
    return this.loadPoster()
      .finally(() => wx.hideLoading())
      .then(() => {
        if (!this.data.composedPoster) {
          wx.showModal({
            title: '海报未生成',
            content: this.data.qrError || '请检查服务端 WECHAT_SECRET、Pillow 依赖，以及 WECHAT_QRCODE_ENV_VERSION=trial',
            showCancel: false
          });
          return;
        }
        wx.showToast({ title: '海报已更新', icon: 'success' });
      });
  },
  savePoster() {
    const path = this.data.composedPoster;
    if (!path) return;
    wx.saveImageToPhotosAlbum({
      filePath: path,
      success: () => wx.showToast({ title: '已保存到相册' }),
      fail: () => wx.showModal({
        title: '保存失败',
        content: '请在设置中允许保存到相册后重试',
        showCancel: false
      })
    });
  },
  saveQrImage() {
    const path = this.data.qrPath || this.data.qrImage;
    if (!path) {
      wx.showToast({ title: '二维码未生成', icon: 'none' });
      return;
    }
    wx.saveImageToPhotosAlbum({
      filePath: path,
      success: () => wx.showToast({ title: '小程序码已保存' }),
      fail: () => wx.showModal({
        title: '保存失败',
        content: '请允许保存到相册，或直接长按小程序码分享',
        showCancel: false
      })
    });
  },
  copyInviteCode() {
    const code = this.data.agent.invite_code || '';
    if (!code) return;
    wx.setClipboardData({
      data: code,
      success: () => wx.showToast({ title: '推广码已复制' })
    });
  },
  copyMaterial(e) {
    const content = e.currentTarget.dataset.content || '';
    if (!content) return;
    wx.setClipboardData({
      data: content,
      success: () => wx.showToast({ title: '已复制' })
    });
  },
  goWithdraw() {
    wx.navigateTo({ url: '/pages/promotion/withdraw' });
  },
  toggleFaq(e) {
    const faqId = Number(e.currentTarget.dataset.id);
    this.setData({ expandedFaqId: this.data.expandedFaqId === faqId ? null : faqId });
  },
  onShareAppMessage() {
    const code = this.data.agent.invite_code || '';
    const beans = (this.data.scanReward && this.data.scanReward.bonus_beans) || 0;
    const title = beans > 0
      ? `${this.data.agent.display_name || '智愿填报'} · 扫码领${beans}星鼎豆`
      : `${this.data.agent.display_name || '智愿填报'} · 高考志愿智能辅助`;
    return {
      title,
      path: `/pages/home/home?invite=${code}`
    };
  }
});
