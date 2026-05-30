const BASE_URL = 'http://127.0.0.1:8001';

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
        reject(new Error(res.data && res.data.detail ? res.data.detail : `请求失败：${res.statusCode}`));
      },
      fail(error) {
        reject(error);
      }
    });
  });
}

module.exports = {
  BASE_URL,
  request
};
