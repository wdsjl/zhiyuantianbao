const { request } = require('../../utils/request');
const { ensureWechatLogin } = require('../../utils/auth');
const { getCurrentUserId } = require('../../utils/membership');

Page({
  data: {
    loading: true,
    agent: {},
    invitees: [],
    commissions: [],
    pendingCommission: 0,
    posterImage: ''
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
          .then(() => request({ url: '/api/referral/dashboard', data: { user_id: Number(userId) } }))
          .then((dashboard) => request({ url: '/api/referral/poster', data: { user_id: Number(userId) } })
            .then((poster) => ({ dashboard, poster }))
            .catch(() => ({ dashboard, poster: null }))
          );
      })
      .then(({ dashboard, poster }) => {
        this.setData({
          loading: false,
          agent: dashboard.agent || {},
          invitees: dashboard.invitees || [],
          commissions: dashboard.commissions || [],
          pendingCommission: dashboard.pending_commission || 0,
          posterImage: poster && poster.image_base64 ? `data:image/png;base64,${poster.image_base64}` : ''
        });
      })
      .catch((error) => {
        this.setData({ loading: false });
        wx.showToast({ title: error.message || '加载失败', icon: 'none' });
      });
  },
  refreshPoster() {
    this.loadDashboard();
  },
  savePoster() {
    const filePath = this._posterFilePath;
    const save = (path) => {
      wx.saveImageToPhotosAlbum({
        filePath: path,
        success: () => wx.showToast({ title: '已保存到相册' }),
        fail: () => wx.showModal({
          title: '保存失败',
          content: '请在设置中允许保存到相册后重试',
          showCancel: false
        })
      });
    };
    if (filePath) {
      save(filePath);
      return;
    }
    if (!this.data.posterImage) return;
    const fsm = wx.getFileSystemManager();
    const tempPath = `${wx.env.USER_DATA_PATH}/referral_poster.png`;
    const base64 = this.data.posterImage.replace(/^data:image\/\w+;base64,/, '');
    fsm.writeFile({
      filePath: tempPath,
      data: base64,
      encoding: 'base64',
      success: () => {
        this._posterFilePath = tempPath;
        save(tempPath);
      },
      fail: () => wx.showToast({ title: '海报保存失败', icon: 'none' })
    });
  },
  onShareAppMessage() {
    const code = this.data.agent.invite_code || '';
    return {
      title: '智愿填报 · 高考志愿智能辅助',
      path: `/pages/home/home?invite=${code}`
    };
  }
});
