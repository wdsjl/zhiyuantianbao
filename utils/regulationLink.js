const EXTERNAL_REGULATION_HINT =
  '招生章程来自阳光高考等教育部官网。该类域名无法在小程序内直接打开，请复制链接后在手机浏览器中查看。';

function isOwnBusinessHost(hostname) {
  const host = String(hostname || '').toLowerCase();
  return host === 'api.zntb.lhyun.net' || host.endsWith('.zntb.lhyun.net');
}

function canOpenInMiniProgramWebview(url) {
  if (!url) return false;
  try {
    const matched = String(url).match(/^https?:\/\/([^/?#]+)/i);
    if (!matched) return false;
    return isOwnBusinessHost(matched[1]);
  } catch (error) {
    return false;
  }
}

function openExternalRegulation(url, options) {
  const opts = options || {};
  const title = opts.title || '打开招生章程';
  const content = opts.content || EXTERNAL_REGULATION_HINT;
  if (!url) {
    wx.showToast({ title: '暂无招生章程链接', icon: 'none' });
    return;
  }
  if (canOpenInMiniProgramWebview(url)) {
    wx.navigateTo({ url: `/pages/webview/webview?url=${encodeURIComponent(url)}` });
    return;
  }
  wx.setClipboardData({
    data: url,
    success: () => {
      wx.showModal({
        title,
        content: `${content}\n\n链接已复制，请粘贴到手机浏览器地址栏打开。`,
        showCancel: false,
        confirmText: '知道了'
      });
    }
  });
}

function copyRegulationLink(url) {
  if (!url) {
    wx.showToast({ title: '暂无招生章程链接', icon: 'none' });
    return;
  }
  wx.setClipboardData({
    data: url,
    success: () => wx.showToast({ title: '链接已复制', icon: 'success' })
  });
}

module.exports = {
  EXTERNAL_REGULATION_HINT,
  canOpenInMiniProgramWebview,
  openExternalRegulation,
  copyRegulationLink
};
