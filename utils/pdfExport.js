const { BASE_URL } = require('./request');

function openPdfFromUrl(path) {
  return new Promise((resolve, reject) => {
    wx.showLoading({ title: '生成 PDF...', mask: true });
    wx.downloadFile({
      url: `${BASE_URL}${path}`,
      success: (downloadRes) => {
        if (downloadRes.statusCode !== 200) {
          reject(new Error('PDF 生成失败'));
          return;
        }
        wx.openDocument({
          filePath: downloadRes.tempFilePath,
          fileType: 'pdf',
          showMenu: true,
          success: () => resolve(downloadRes.tempFilePath),
          fail: () => reject(new Error('PDF 打开失败'))
        });
      },
      fail: () => reject(new Error('PDF 下载失败')),
      complete: () => wx.hideLoading()
    });
  });
}

module.exports = {
  openPdfFromUrl
};
