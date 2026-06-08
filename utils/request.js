// 生产环境 API 地址；本地调试可临时改回 http://127.0.0.1:8001
const BASE_URL = 'https://api.zntb.lhyun.net';

function parseApiDetail(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join('；');
  }
  return String(detail);
}

function formatRequestError(error) {
  if (!error) return '请求失败';
  if (error.errMsg) return error.errMsg;
  if (error.message) return error.message;
  return '请求失败';
}

function getMiniProgramAppId() {
  try {
    return wx.getAccountInfoSync().miniProgram.appId || '';
  } catch (e) {
    return '';
  }
}

function runNetworkDiagnostic() {
  const appId = getMiniProgramAppId();
  const start = Date.now();
  return new Promise((resolve) => {
    wx.request({
      url: `${BASE_URL}/health`,
      method: 'GET',
      timeout: 15000,
      success(res) {
        resolve({
          ok: res.statusCode >= 200 && res.statusCode < 300,
          appId,
          baseUrl: BASE_URL,
          statusCode: res.statusCode,
          body: res.data,
          elapsedMs: Date.now() - start,
          errMsg: ''
        });
      },
      fail(error) {
        resolve({
          ok: false,
          appId,
          baseUrl: BASE_URL,
          statusCode: 0,
          body: null,
          elapsedMs: Date.now() - start,
          errMsg: error.errMsg || 'request:fail'
        });
      }
    });
  });
}

function buildDiagnosticReport(result) {
  const lines = [
    `AppID：${result.appId || '未知'}`,
    `接口：${result.baseUrl}/health`,
    `结果：${result.ok ? '连接成功' : '连接失败'}`,
    `耗时：${result.elapsedMs}ms`
  ];
  if (result.statusCode) lines.push(`HTTP：${result.statusCode}`);
  if (result.body) lines.push(`返回：${JSON.stringify(result.body)}`);
  if (result.errMsg) lines.push(`错误：${result.errMsg}`);

  if (!result.ok && result.errMsg.includes('domain list')) {
    lines.push('提示：域名未生效。请确认公众平台 AppID 与开发者工具一致，并删除手机上的小程序后重新扫码。');
  } else if (!result.ok && result.appId === 'touristappid') {
    lines.push('提示：当前为游客 AppID，合法域名不会生效。请在开发者工具填写正式 AppID：wx58ed9703d22d85c2');
  } else if (!result.ok) {
    lines.push('提示：浏览器能打开但小程序不行时，请在手机预览右上角 ··· → 开发调试 → 打开调试 后重试。');
  }
  return lines.join('\n');
}

function request(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: options.timeout || 30000,
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
        console.error('[request fail]', options.url, error);
        reject(error);
      }
    });
  });
}

module.exports = {
  BASE_URL,
  request,
  formatRequestError,
  runNetworkDiagnostic,
  buildDiagnosticReport,
  getMiniProgramAppId
};
