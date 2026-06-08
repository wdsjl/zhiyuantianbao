const { BASE_URL, formatRequestError } = require('./request');

function buildDownloadError(downloadRes, failError) {
  if (failError && failError.errMsg) {
    const message = formatRequestError(failError);
    if (message.includes('domain list')) {
      return '下载域名未配置。请在微信公众平台 → 服务器域名 → downloadFile合法域名 添加 https://api.zntb.lhyun.net';
    }
    return message;
  }
  if (downloadRes && downloadRes.statusCode === 404) {
    return '报告不存在，请先生成报告后再导出';
  }
  if (downloadRes && downloadRes.statusCode) {
    return `PDF 生成失败（HTTP ${downloadRes.statusCode}）`;
  }
  return 'PDF 下载失败，请检查网络与 downloadFile 合法域名';
}

function openPdfFromUrl(path) {
  return new Promise((resolve, reject) => {
    wx.showLoading({ title: '生成 PDF...', mask: true });
    wx.downloadFile({
      url: `${BASE_URL}${path}`,
      success: (downloadRes) => {
        if (downloadRes.statusCode !== 200) {
          reject(new Error(buildDownloadError(downloadRes, null)));
          return;
        }
        wx.openDocument({
          filePath: downloadRes.tempFilePath,
          fileType: 'pdf',
          showMenu: true,
          success: () => resolve(downloadRes.tempFilePath),
          fail: (error) => reject(new Error(error.errMsg || 'PDF 打开失败'))
        });
      },
      fail: (error) => reject(new Error(buildDownloadError(null, error))),
      complete: () => wx.hideLoading()
    });
  });
}

module.exports = {
  openPdfFromUrl
};
