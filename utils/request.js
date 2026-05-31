const BASE_URL = 'http://127.0.0.1:8001';
const LOCAL_FALLBACK_URL = 'http://localhost:8001';

function getBaseUrls() {
  const customBaseUrl = wx.getStorageSync('apiBaseUrl');
  if (customBaseUrl) return [customBaseUrl];
  return [BASE_URL, LOCAL_FALLBACK_URL];
}

function request(options) {
  return new Promise((resolve, reject) => {
    const baseUrls = getBaseUrls();
    let currentIndex = 0;

    function send() {
      const baseUrl = baseUrls[currentIndex];
      wx.request({
        url: `${baseUrl}${options.url}`,
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
  request
};
