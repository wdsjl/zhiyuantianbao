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

function parseArrayBufferError(data) {
  if (!data) return '';
  try {
    const text = String.fromCharCode.apply(null, new Uint8Array(data));
    const parsed = JSON.parse(text);
    return parsed.detail || parsed.message || '';
  } catch (error) {
    return '';
  }
}

function buildRequestError(statusCode, data) {
  if (statusCode === 404) {
    return '报告不存在，请先生成报告后再导出';
  }
  const detail = parseArrayBufferError(data);
  if (detail) return detail;
  if (statusCode) return `PDF 生成失败（HTTP ${statusCode}）`;
  return 'PDF 生成失败，请稍后重试';
}

function openDocument(filePath) {
  return new Promise((resolve, reject) => {
    wx.openDocument({
      filePath,
      fileType: 'pdf',
      showMenu: true,
      success: () => resolve(filePath),
      fail: (error) => reject(new Error(error.errMsg || 'PDF 打开失败'))
    });
  });
}

function writePdfBuffer(buffer) {
  return new Promise((resolve, reject) => {
    const filePath = `${wx.env.USER_DATA_PATH}/export_${Date.now()}.pdf`;
    wx.getFileSystemManager().writeFile({
      filePath,
      data: buffer,
      success: () => resolve(filePath),
      fail: (error) => reject(new Error(error.errMsg || 'PDF 保存失败'))
    });
  });
}

function openPdfFromPost(path, data) {
  return new Promise((resolve, reject) => {
    wx.showLoading({ title: '生成 PDF...', mask: true });
    wx.request({
      url: `${BASE_URL}${path}`,
      method: 'POST',
      data: data || {},
      header: { 'content-type': 'application/json' },
      responseType: 'arraybuffer',
      success: (res) => {
        if (res.statusCode !== 200) {
          reject(new Error(buildRequestError(res.statusCode, res.data)));
          return;
        }
        writePdfBuffer(res.data)
          .then((filePath) => openDocument(filePath))
          .then(resolve)
          .catch(reject);
      },
      fail: (error) => reject(new Error(formatRequestError(error))),
      complete: () => wx.hideLoading()
    });
  });
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
        openDocument(downloadRes.tempFilePath).then(resolve).catch(reject);
      },
      fail: (error) => reject(new Error(buildDownloadError(null, error))),
      complete: () => wx.hideLoading()
    });
  });
}

module.exports = {
  openPdfFromUrl,
  openPdfFromPost
};
