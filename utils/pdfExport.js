const { BASE_URL, formatRequestError } = require('./request');

function sanitizeFileName(name) {
  const text = String(name || '导出')
    .replace(/[/\\:*?"<>|\r\n\t]/g, '')
    .trim();
  return text || '导出';
}

function ensurePdfExtension(fileName) {
  const safeName = sanitizeFileName(fileName);
  return safeName.toLowerCase().endsWith('.pdf') ? safeName : `${safeName}.pdf`;
}

function buildStudentPdfFileName(profile, label) {
  const name = sanitizeFileName(
    (profile && (profile.name || profile.studentName || profile.student_name)) || '学生'
  );
  return ensurePdfExtension(`${name}的${sanitizeFileName(label)}`);
}

function decodePdfFilename(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  try {
    return decodeURIComponent(text);
  } catch (error) {
    return text;
  }
}

function resolveResponseFileName(res, fallback) {
  const headers = res.header || {};
  const fromHeader = headers['X-Pdf-Filename'] || headers['x-pdf-filename'];
  const decoded = decodePdfFilename(fromHeader);
  return ensurePdfExtension(decoded || fallback || '学生的报告.pdf');
}

function getFileSystem() {
  return wx.getFileSystemManager();
}

function buildInternalPdfPath() {
  return `${wx.env.USER_DATA_PATH}/ztb_${Date.now()}.pdf`;
}

function writeBinaryFile(filePath, data) {
  return new Promise((resolve, reject) => {
    getFileSystem().writeFile({
      filePath,
      data,
      success: () => resolve(filePath),
      fail: (error) => reject(new Error(error.errMsg || 'PDF 保存失败'))
    });
  });
}

function readBinaryFile(filePath) {
  return new Promise((resolve, reject) => {
    getFileSystem().readFile({
      filePath,
      success: (res) => resolve(res.data),
      fail: (error) => reject(new Error(error.errMsg || 'PDF 读取失败'))
    });
  });
}

function persistPdfData(data, displayFileName) {
  const filePath = buildInternalPdfPath();
  const fileName = ensurePdfExtension(displayFileName);
  return writeBinaryFile(filePath, data).then(() => ({ filePath, fileName }));
}

function persistPdfFromTemp(tempFilePath, displayFileName) {
  const filePath = buildInternalPdfPath();
  const fileName = ensurePdfExtension(displayFileName);
  const fs = getFileSystem();
  return new Promise((resolve, reject) => {
    fs.copyFile({
      srcPath: tempFilePath,
      destPath: filePath,
      success: () => resolve({ filePath, fileName }),
      fail: () => {
        readBinaryFile(tempFilePath)
          .then((data) => writeBinaryFile(filePath, data))
          .then(() => resolve({ filePath, fileName }))
          .catch(reject);
      }
    });
  });
}

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
      success: () => resolve({ filePath, action: 'preview' }),
      fail: (error) => reject(new Error(error.errMsg || 'PDF 打开失败'))
    });
  });
}

function sharePdfToWeChat(filePath, fileName) {
  return new Promise((resolve, reject) => {
    if (!wx.shareFileMessage) {
      reject(new Error('微信版本过低，请升级后使用「发送到微信」'));
      return;
    }
    const displayName = ensurePdfExtension(fileName);
    wx.shareFileMessage({
      filePath,
      fileName: displayName,
      success: () => resolve({ filePath, fileName: displayName, action: 'share' }),
      fail: (error) => reject(new Error(error.errMsg || '发送失败，请重试'))
    });
  });
}

function requestPdfBuffer(path, data) {
  return new Promise((resolve, reject) => {
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
        resolve(res);
      },
      fail: (error) => reject(new Error(formatRequestError(error)))
    });
  });
}

function downloadPdfFile(path) {
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: `${BASE_URL}${path}`,
      success: resolve,
      fail: reject
    });
  });
}

function preparePdfFromPost(path, data, options) {
  const opts = options || {};
  wx.showLoading({ title: '生成 PDF...', mask: true });
  return requestPdfBuffer(path, data)
    .then((res) => {
      const fileName = resolveResponseFileName(res, opts.fileName);
      return persistPdfData(res.data, fileName);
    })
    .finally(() => wx.hideLoading());
}

function preparePdfFromUrl(path, options) {
  const opts = options || {};
  const fileName = ensurePdfExtension(opts.fileName || '学生的填报志愿.pdf');
  wx.showLoading({ title: '生成 PDF...', mask: true });
  return downloadPdfFile(path)
    .then((downloadRes) => {
      if (downloadRes.statusCode !== 200) {
        return Promise.reject(new Error(buildDownloadError(downloadRes, null)));
      }
      return persistPdfFromTemp(downloadRes.tempFilePath, fileName);
    })
    .finally(() => wx.hideLoading());
}

function openPdfFromPost(path, data, options) {
  const opts = options || {};
  return preparePdfFromPost(path, data, opts).then(({ filePath, fileName }) => {
    if (opts.mode === 'preview') return openDocument(filePath);
    return sharePdfToWeChat(filePath, fileName);
  });
}

function openPdfFromUrl(path, options) {
  const opts = options || {};
  return preparePdfFromUrl(path, opts).then(({ filePath, fileName }) => {
    if (opts.mode === 'preview') return openDocument(filePath);
    return sharePdfToWeChat(filePath, fileName);
  });
}

module.exports = {
  openPdfFromUrl,
  openPdfFromPost,
  preparePdfFromPost,
  preparePdfFromUrl,
  sharePdfToWeChat,
  openDocument,
  buildStudentPdfFileName
};
