// 生产环境 API 地址；本地调试可临时改回 http://127.0.0.1:8001
const BASE_URL = 'https://api.zntb.lhyun.net';

function parseApiDetail(detail) {
  if (detail === null || detail === undefined || detail === '') return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (!item) return '';
      if (typeof item === 'string') return item;
      return item.msg || item.message || JSON.stringify(item);
    }).filter(Boolean).join('；');
  }
  if (typeof detail === 'object') {
    if (detail.message) return parseApiDetail(detail.message);
    if (detail.msg) return String(detail.msg);
    if (detail.detail) return parseApiDetail(detail.detail);
    if (detail.error) return parseApiDetail(detail.error);
    try {
      return JSON.stringify(detail);
    } catch (error) {
      return '请求失败';
    }
  }
  return String(detail);
}

function formatRequestError(error) {
  if (!error) return '请求失败';
  if (error.errMsg) {
    if (error.errMsg.includes('request:fail')) {
      return `无法连接后端（${BASE_URL}），请确认服务已启动`;
    }
    return error.errMsg;
  }
  if (error.message) return error.message;
  return '请求失败';
}

function request(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'content-type': 'application/json',
        ...(options.header || {})
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        const detail = parseApiDetail(res.data && res.data.detail);
        reject(new Error(detail || `请求失败：${res.statusCode}`));
      },
      fail(error) {
        reject(error);
      }
    });
  });
}

module.exports = {
  BASE_URL,
  request,
  formatRequestError
};
