const { request } = require('../../utils/request');
const { ensureWechatLogin } = require('../../utils/auth');
const { getCurrentUserId } = require('../../utils/membership');

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
    composedPoster: ''
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
            request({ url: '/api/referral/poster', data: { user_id: Number(userId), template_key: this.data.templateKey } }),
            request({ url: '/api/referral/materials' })
          ]));
      })
      .then(([dashboard, poster, materialsRes]) => {
        const qrImage = poster && poster.image_base64 ? `data:image/png;base64,${poster.image_base64}` : '';
        this.setData({
          loading: false,
          agent: dashboard.agent || {},
          invitees: dashboard.invitees || [],
          commissions: dashboard.commissions || [],
          pendingCommission: dashboard.pending_commission || 0,
          wallet: dashboard.wallet || {},
          rangeStats: dashboard.range_stats || {},
          materials: materialsRes.list || [],
          templates: poster.templates || [],
          templateKey: (poster.template && poster.template.template_key) || 'blue',
          qrImage,
          composedPoster: ''
        });
      })
      .catch((error) => {
        this.setData({ loading: false });
        wx.showToast({ title: error.message || '加载失败', icon: 'none' });
      });
  },
  onDaysChange(e) {
    const days = Number(e.currentTarget.dataset.days || 30);
    this.setData({ days }, () => this.loadDashboard());
  },
  onTemplateChange(e) {
    const templateKey = e.currentTarget.dataset.key;
    this.setData({ templateKey, composedPoster: '' }, () => {
      const userId = getCurrentUserId();
      request({ url: '/api/referral/poster', data: { user_id: Number(userId), template_key: templateKey } })
        .then((poster) => {
          this.setData({
            qrImage: poster.image_base64 ? `data:image/png;base64,${poster.image_base64}` : this.data.qrImage
          });
        });
    });
  },
  composePoster() {
    const template = (this.data.templates || []).find((item) => item.template_key === this.data.templateKey)
      || { bg_color: '#1677ff', text_color: '#ffffff' };
    const ctx = wx.createCanvasContext('posterCanvas', this);
    const width = 300;
    const height = 450;
    ctx.setFillStyle(template.bg_color || '#1677ff');
    ctx.fillRect(0, 0, width, height);
    ctx.setFillStyle(template.text_color || '#ffffff');
    ctx.setFontSize(22);
    ctx.fillText('智愿填报', 24, 48);
    ctx.setFontSize(16);
    ctx.fillText(this.data.agent.display_name || '专属达人', 24, 82);
    ctx.setFontSize(14);
    ctx.fillText('高考志愿智能辅助', 24, 108);
    ctx.setFontSize(12);
    ctx.fillText(`推广码 ${this.data.agent.invite_code || ''}`, 24, height - 72);
    ctx.fillText('扫码领取专属权益', 24, height - 48);
    if (!this.data.qrImage) {
      wx.showToast({ title: '二维码未生成', icon: 'none' });
      return;
    }
    ctx.drawImage(this.data.qrImage, 72, 140, 156, 156);
    ctx.draw(false, () => {
      wx.canvasToTempFilePath({
        canvasId: 'posterCanvas',
        success: (res) => this.setData({ composedPoster: res.tempFilePath }),
        fail: () => wx.showToast({ title: '海报生成失败', icon: 'none' })
      }, this);
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
  onShareAppMessage() {
    const code = this.data.agent.invite_code || '';
    return {
      title: `${this.data.agent.display_name || '智愿填报'} · 高考志愿智能辅助`,
      path: `/pages/home/home?invite=${code}`
    };
  }
});
