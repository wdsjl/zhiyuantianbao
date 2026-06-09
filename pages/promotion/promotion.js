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
    if (!userId) return;
    request({ url: '/api/referral/poster', data: { user_id: Number(userId), template_key: this.data.templateKey } })
      .then((poster) => this.applyPosterData(poster))
      .catch((error) => {
        this.setData({ qrError: error.message || '二维码加载失败', qrImage: '', qrPath: '' });
      });
  },
  applyPosterData(poster) {
    const base64 = poster && poster.image_base64 ? poster.image_base64 : '';
    const scanReward = poster.scan_reward || this.data.scanReward || {};
    const qrError = poster.qr_error || '';
    if (!base64) {
      this.setData({
        templates: poster.templates || [],
        templateKey: (poster.template && poster.template.template_key) || this.data.templateKey,
        scanReward,
        qrImage: '',
        qrPath: '',
        qrError: qrError || '未获取到小程序码，请检查服务端 WECHAT_SECRET 配置'
      });
      return;
    }
    return base64ToTempFilePath(base64, `poster_qr_${poster.invite_code || 'agent'}.png`)
      .then((qrPath) => {
        this.setData({
          templates: poster.templates || [],
          templateKey: (poster.template && poster.template.template_key) || this.data.templateKey,
          scanReward,
          qrPath,
          qrImage: qrPath,
          qrError: ''
        });
      })
      .catch((error) => {
        this.setData({
          templates: poster.templates || [],
          templateKey: (poster.template && poster.template.template_key) || this.data.templateKey,
          scanReward,
          qrImage: '',
          qrPath: '',
          qrError: error.message || qrError || '二维码解析失败'
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
    const template = (this.data.templates || []).find((item) => item.template_key === this.data.templateKey)
      || { bg_color: '#1677ff', text_color: '#ffffff' };
    const qrPath = this.data.qrPath || this.data.qrImage;
    if (!qrPath) {
      wx.showModal({
        title: '二维码未就绪',
        content: this.data.qrError || '请稍后重试，或先使用下方小程序码长按分享',
        showCancel: false
      });
      return;
    }
    const rewardText = (this.data.scanReward && this.data.scanReward.reward_text) || '扫码领取专属权益';
    const ctx = wx.createCanvasContext('posterCanvas', this);
    const width = 300;
    const height = 480;
    ctx.setFillStyle(template.bg_color || '#1677ff');
    ctx.fillRect(0, 0, width, height);
    ctx.setFillStyle(template.text_color || '#ffffff');
    ctx.setFontSize(22);
    ctx.fillText('智愿填报', 24, 48);
    ctx.setFontSize(16);
    ctx.fillText(this.data.agent.display_name || '专属达人', 24, 82);
    ctx.setFontSize(14);
    ctx.fillText('高考志愿智能辅助', 24, 108);
    ctx.setFontSize(13);
    ctx.fillText(rewardText, 24, 132);
    ctx.setFontSize(12);
    ctx.fillText(`推广码 ${this.data.agent.invite_code || ''}`, 24, height - 72);
    ctx.fillText('微信扫一扫小程序码', 24, height - 48);
    ctx.drawImage(qrPath, 72, 156, 156, 156);
    ctx.draw(false, () => {
      setTimeout(() => {
        wx.canvasToTempFilePath({
          canvasId: 'posterCanvas',
          width,
          height,
          destWidth: width * 2,
          destHeight: height * 2,
          success: (res) => this.setData({ composedPoster: res.tempFilePath }),
          fail: () => wx.showToast({ title: '海报生成失败', icon: 'none' })
        }, this);
      }, 300);
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
