Page({
  data: {
    url: ''
  },
  onLoad(options) {
    const url = decodeURIComponent(options.url || '');
    if (!url) {
      wx.showToast({ title: '链接无效', icon: 'none' });
      return;
    }
    this.setData({ url });
  }
});
