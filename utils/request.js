const PRODUCTION_BASE_URL = 'https://api.zntb.lhyun.net';
const LOCAL_BASE_URLS = ['http://127.0.0.1:8001', 'http://localhost:8001'];
const BASE_URL = PRODUCTION_BASE_URL;

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl || '').replace(/\/+$/, '');
}

function isReleaseEnvironment() {
  try {
    const accountInfo = wx.getAccountInfoSync();
    return accountInfo && accountInfo.miniProgram && accountInfo.miniProgram.envVersion === 'release';
  } catch (error) {
    return false;
  }
}

function getBaseUrls() {
  const customBaseUrl = normalizeBaseUrl(wx.getStorageSync('apiBaseUrl'));
  if (customBaseUrl) return [customBaseUrl];
  if (isReleaseEnvironment()) return [PRODUCTION_BASE_URL];
  return LOCAL_BASE_URLS.concat(PRODUCTION_BASE_URL);
}

function buildUrl(path, baseUrl) {
  return `${normalizeBaseUrl(baseUrl || getBaseUrls()[0])}${path}`;
}

function request(options) {
  return new Promise((resolve, reject) => {
    const baseUrls = getBaseUrls();
    let currentIndex = 0;

    function send() {
      const baseUrl = baseUrls[currentIndex];
      wx.request({
        url: buildUrl(options.url, baseUrl),
        method: options.method || 'GET',
        data: options.data || {},
        timeout: options.timeout || 8000,
        header: {
          'content-type': 'application/json',
          ...(options.header || {})
        },
        success(res) {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
            return;
          }
          reject(new Error(res.data && res.data.detail ? res.data.detail : `请求失败：${res.statusCode}`));
        },
        fail(error) {
          currentIndex += 1;
          if (currentIndex < baseUrls.length) {
            send();
            return;
          }
          reject(error);
        }
      });
    }

    send();
  });
}

module.exports = {
  BASE_URL,
  PRODUCTION_BASE_URL,
  buildUrl,
  getBaseUrls,
  request
};
