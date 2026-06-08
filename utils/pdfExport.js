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
  return ensurePdfExtension(fromHeader || fallback || `学生的报告.pdf`);
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
      reject(new Error('当前微信版本较低，请升级后使用「转发给微信好友」'));
      return;
    }
    wx.shareFileMessage({
      filePath,
      fileName: ensurePdfExtension(fileName),
      success: () => resolve({ filePath, fileName, action: 'share' }),
      fail: (error) => reject(new Error(error.errMsg || '转发失败，请重试'))
    });
  });
}

function presentPdfActions(filePath, fileName) {
  const displayName = ensurePdfExtension(fileName);
  return new Promise((resolve, reject) => {
    wx.showActionSheet({
      itemList: ['打开预览', `转发给微信好友（${displayName}）`],
      success: (res) => {
        if (res.tapIndex === 0) {
          openDocument(filePath).then(resolve).catch(reject);
          return;
        }
        if (res.tapIndex === 1) {
          sharePdfToWeChat(filePath, displayName).then(resolve).catch(reject);
          return;
        }
        reject(new Error('已取消'));
      },
      fail: (error) => {
        if (error && error.errMsg && error.errMsg.includes('cancel')) {
          reject(new Error('已取消'));
          return;
        }
        reject(new Error((error && error.errMsg) || '操作失败'));
      }
    });
  });
}

function openPdfFromPost(path, data, options) {
  const opts = options || {};
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
        const fileName = resolveResponseFileName(res, opts.fileName);
        persistPdfData(res.data, fileName)
          .then((filePath) => presentPdfActions(filePath, fileName))
          .then(resolve)
          .catch(reject);
      },
      fail: (error) => reject(new Error(formatRequestError(error))),
      complete: () => wx.hideLoading()
    });
  });
}

function finishDownloadedPdf(downloadRes, fileName) {
  if (downloadRes.statusCode !== 200) {
    return Promise.reject(new Error(buildDownloadError(downloadRes, null)));
  }
  const savedPath = downloadRes.filePath || downloadRes.tempFilePath;
  return persistPdfFromTemp(savedPath, fileName)
    .then((finalPath) => presentPdfActions(finalPath, fileName));
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
  return new Promise((resolve, reject) => {
    wx.showLoading({ title: '生成 PDF...', mask: true });
    const finish = (error, result) => {
      wx.hideLoading();
      if (error) reject(error);
      else resolve(result);
    };
    downloadPdfFile(path, namedPath)
      .catch(() => downloadPdfFile(path, ''))
      .then((downloadRes) => finishDownloadedPdf(downloadRes, fileName))
      .then((result) => finish(null, result))
      .catch((error) => finish(new Error(error.message || 'PDF 下载失败')));
  });
}

module.exports = {
  openPdfFromUrl,
  openPdfFromPost,
  buildStudentPdfFileName
};
