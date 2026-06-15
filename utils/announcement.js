const { BASE_URL } = require('./request');

const TYPE_OPTIONS = ['', '招生公告', '招生章程', '招生计划', '招生简章', '招生官网', '录取信息'];

function getAnnouncementFileUrl(announcementId) {
  return `${BASE_URL}/api/announcements/${announcementId}/file`;
}

function isDocumentAnnouncement(item) {
  const ext = String(item.file_ext || '').toLowerCase();
  const url = String(item.url || item.file_url || '').toLowerCase();
  return ['pdf', 'xls', 'xlsx', 'csv'].includes(ext)
    || url.endsWith('.pdf')
    || url.endsWith('.xlsx')
    || url.endsWith('.xls');
}

function openAnnouncement(item) {
  if (!item || !item.announcement_id) return;
  const url = item.url || item.file_url;
  if (!url) {
    wx.showToast({ title: '暂无链接', icon: 'none' });
    return;
  }
  if (isDocumentAnnouncement(item)) {
    wx.showLoading({ title: '打开文件中...' });
    wx.downloadFile({
      url: getAnnouncementFileUrl(item.announcement_id),
      success(res) {
        wx.openDocument({
          filePath: res.tempFilePath,
          showMenu: true,
          fail() {
            wx.showToast({ title: '无法打开文件', icon: 'none' });
          }
        });
      },
      fail() {
        wx.showToast({ title: '文件下载失败', icon: 'none' });
      },
      complete() {
        wx.hideLoading();
      }
    });
    return;
  }
  const encoded = encodeURIComponent(url);
  wx.navigateTo({ url: `/pages/webview/webview?url=${encoded}` });
}

module.exports = {
  TYPE_OPTIONS,
  getAnnouncementFileUrl,
  isDocumentAnnouncement,
  openAnnouncement
};
