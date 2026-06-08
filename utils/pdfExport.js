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

function resolveResponseFileName(res, fallback) {
  const headers = res.header || {};
  const fromHeader = headers['X-Pdf-Filename'] || headers['x-pdf-filename'];
  return ensurePdfExtension(fromHeader || fallback || '学生的报告.pdf');
}

function getFileSystem() {
  return wx.getFileSystemManager();
}

function buildFilePath(fileName) {
  return `${wx.env.USER_DATA_PATH}/${ensurePdfExtension(fileName)}`;
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

function persistPdfData(data, fileName) {
  return writeBinaryFile(buildFilePath(fileName), data);
}

function persistPdfFromTemp(tempFilePath, fileName) {
  const destPath = buildFilePath(fileName);
  const fs = getFileSystem();
  return new Promise((resolve, reject) => {
    fs.copyFile({
      srcPath: tempFilePath,
      destPath,
      success: () => resolve(destPath),
      fail: () => {
        readBinaryFile(tempFilePath)
          .then((data) => writeBinaryFile(destPath, data))
          .then(resolve)
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
      reject(new Error('当前微信版本较低，请升级微信后使用转发功能'));
      return;
    }
    wx.shareFileMessage({
      filePath,
      fileName: ensurePdfExtension(fileName),
      success: () => resolve({ filePath, fileName: ensurePdfExtension(fileName), action: 'share' }),
      fail: (error) => reject(new Error(error.errMsg || '转发失败，请重试'))
    });
  });
}

function deliverPdf(filePath, fileName, options) {
  const opts = options || {};
  const displayName = ensurePdfExtension(fileName);
  if (opts.mode === 'share') {
    return sharePdfToWeChat(filePath, displayName);
  }
  if (opts.mode === 'preview') {
    return openDocument(filePath);
  }
  return new Promise((resolve, reject) => {
    wx.showModal({
      title: 'PDF 已生成',
      content: `文件名：${displayName}\n\n请点击「转发到微信」发送给文件传输助手或好友。\n\n注意：不要从预览页右上角转发，那样文件名会变成乱码。`,
      confirmText: '转发到微信',
      cancelText: '打开预览',
      success: (res) => {
        if (res.confirm) {
          sharePdfToWeChat(filePath, displayName).then(resolve).catch(reject);
          return;
        }
        if (res.cancel) {
          openDocument(filePath).then(resolve).catch(reject);
          return;
        }
        reject(new Error('已取消'));
      },
      fail: reject
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

function openPdfFromPost(path, data, options) {
  const opts = options || {};
  wx.showLoading({ title: '生成 PDF...', mask: true });
  return requestPdfBuffer(path, data)
    .then((res) => {
      const fileName = resolveResponseFileName(res, opts.fileName);
      return persistPdfData(res.data, fileName).then((filePath) => ({
        filePath,
        fileName
      }));
    })
    .then(({ filePath, fileName }) => deliverPdf(filePath, fileName, opts))
    .finally(() => wx.hideLoading());
}

function finishDownloadedPdf(downloadRes, fileName) {
  if (downloadRes.statusCode !== 200) {
    return Promise.reject(new Error(buildDownloadError(downloadRes, null)));
  }
  const savedPath = downloadRes.filePath || downloadRes.tempFilePath;
  return persistPdfFromTemp(savedPath, fileName);
}

function downloadPdfFile(path, filePath) {
  return new Promise((resolve, reject) => {
    const params = {
      url: `${BASE_URL}${path}`,
      success: resolve,
      fail: reject
    };
    if (filePath) params.filePath = filePath;
    wx.downloadFile(params);
  });
}

function openPdfFromUrl(path, options) {
  const opts = options || {};
  const fileName = ensurePdfExtension(opts.fileName || '学生的填报志愿.pdf');
  const namedPath = buildFilePath(fileName);
  wx.showLoading({ title: '生成 PDF...', mask: true });
  return downloadPdfFile(path, namedPath)
    .catch(() => downloadPdfFile(path, ''))
    .then((downloadRes) => finishDownloadedPdf(downloadRes, fileName))
    .then((filePath) => deliverPdf(filePath, fileName, opts))
    .finally(() => wx.hideLoading());
}

function preparePdfFromUrl(path, options) {
  const opts = options || {};
  const fileName = ensurePdfExtension(opts.fileName || '学生的填报志愿.pdf');
  const namedPath = buildFilePath(fileName);
  wx.showLoading({ title: '生成 PDF...', mask: true });
  return downloadPdfFile(path, namedPath)
    .catch(() => downloadPdfFile(path, ''))
    .then((downloadRes) => finishDownloadedPdf(downloadRes, fileName))
    .then((filePath) => ({ filePath, fileName }))
    .finally(() => wx.hideLoading());
}

function preparePdfFromPost(path, data, options) {
  const opts = options || {};
  wx.showLoading({ title: '生成 PDF...', mask: true });
  return requestPdfBuffer(path, data)
    .then((res) => {
      const fileName = resolveResponseFileName(res, opts.fileName);
      return persistPdfData(res.data, fileName).then((filePath) => ({
        filePath,
        fileName
      }));
    })
    .finally(() => wx.hideLoading());
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
